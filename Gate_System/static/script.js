// Update intervals
const STATS_UPDATE_INTERVAL = 5000; // 5 seconds for fast updates
const VEHICLE_CHECK_INTERVAL = 3000; // 3 seconds for vehicle info
const RFID_CHECK_INTERVAL = 2000; // 2 seconds for RFID status
const EVENT_CHECK_INTERVAL = 1500; // 1.5 seconds for event polling

// Auto-clear timer removed - sidebar now shows previous vehicle
let isUpdating = false;
let lastVehicleData = null;
let currentRfidData = null;
let workflowActive = false;
let lastShownEvent = null; // Track last shown event ID

document.addEventListener('DOMContentLoaded', function () {
  // Modal functionality
  const openModal = (modalId) => {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('show');
  };

  const closeModal = (modal) => {
    if (modal) modal.classList.remove('show');
  };

  // Modal event listeners
  const reportBtn = document.getElementById('report-violation-btn');
  if (reportBtn) reportBtn.onclick = () => openModal('report-violation-modal');

  const issuePassBtn = document.getElementById('issue-pass-btn');
  if (issuePassBtn) issuePassBtn.onclick = () => openModal('issue-pass-modal');

  // Close modal logic
  const allModals = document.querySelectorAll('.modal-overlay');
  allModals.forEach((modal) => {
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.onclick = () => closeModal(modal);
    modal.onclick = (event) => {
      if (event.target === modal) closeModal(modal);
    };
  });

  // Clear buttons
  const clearBtn = document.getElementById('clear-btn');
  if (clearBtn) clearBtn.onclick = clearInfo;

  const clearRfidBtn = document.getElementById('clear-rfid-btn');
  if (clearRfidBtn) clearRfidBtn.onclick = clearRfid;

  // Deny entry button - use event delegation
  document.addEventListener('click', function (e) {
    if (e.target.closest('#deny-entry-btn')) {
      e.preventDefault();
      showDenyNotification();
    }
  });

  // Separate functions for different update frequencies
  async function updateStats() {
    try {
      const response = await fetch('/api/dashboard');
      if (response.ok) {
        const data = await response.json();
        if (data.dashboard_stats) {
          updateParkingStatus(data.dashboard_stats.parking || {});
          updateVehicleCounts(data.dashboard_stats.vehicle_counts || {});
          updateAllocations(data.dashboard_stats.allocations || {});
        }
      }
    } catch (error) {
      console.error('Stats update error:', error);
    }
    setTimeout(updateStats, STATS_UPDATE_INTERVAL);
  }

  async function checkVehicleInfo() {
    try {
      const response = await fetch('/api/vehicle_info');
      if (response.ok) {
        const data = await response.json();
        const vehicleData = data.vehicle_info || {};

        // Only update if vehicle data changed
        if (JSON.stringify(vehicleData) !== JSON.stringify(lastVehicleData)) {
          updateVehicleInfo(vehicleData);
          lastVehicleData = vehicleData;
        }
      }
    } catch (error) {
      console.error('Vehicle check error:', error);
    }
    setTimeout(checkVehicleInfo, VEHICLE_CHECK_INTERVAL);
  }

  async function checkRfidStatus() {
    try {
      const response = await fetch('/api/rfid_status');
      if (response.ok) {
        const data = await response.json();
        updateRfidStatus(data.rfid_active, data.current_rfid);
      }
    } catch (error) {
      console.error('RFID check error:', error);
    }
    setTimeout(checkRfidStatus, RFID_CHECK_INTERVAL);
  }

  async function checkLatestEvent() {
    try {
      const response = await fetch('/api/latest_event');
      if (response.ok) {
        const data = await response.json();
        const event = data.event;

        // Only show popup if this is a new event and it's an entry
        if (event && event.id !== lastShownEvent && event.event_type === 'entry') {
          // Show popup for entry event
          showVehicleEntryPopup(event.event_data);

          // Mark event as handled
          await acknowledgeEvent(event.id);

          // Update last shown event
          lastShownEvent = event.id;
        }
      }
    } catch (error) {
      console.error('Event check error:', error);
    }
    setTimeout(checkLatestEvent, EVENT_CHECK_INTERVAL);
  }

  async function acknowledgeEvent(eventId) {
    try {
      await fetch('/api/ack_event', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ event_id: eventId })
      });
    } catch (error) {
      console.error('Error acknowledging event:', error);
    }
  }

  clearInfo();
  updateStats();
  checkVehicleInfo();
  checkRfidStatus();
  checkLatestEvent();
  initializeVideoFeed();
});

function showVehicleEntryPopup(data) {
  const popup = document.getElementById('vehicle-entry-popup');
  const backdrop = document.getElementById('vehicle-entry-backdrop');

  // Update popup content
  document.getElementById('popup-plate').textContent = data.plate || 'Unknown';
  document.getElementById('popup-owner').textContent = data.owner || 'Unknown';
  document.getElementById('popup-vehicle').textContent = data.vehicle || 'Unknown';
  document.getElementById('popup-color').textContent = data.color || 'Unknown';
  document.getElementById('popup-owner-type').textContent = data.role || data.ownerType || 'visitor';
  document.getElementById('popup-time').textContent = data.timestamp || data.time || '-';

  // Show backdrop and popup
  backdrop.style.display = 'block';
  popup.style.display = 'block';

  // Hide after 5 seconds
  setTimeout(() => {
    backdrop.style.display = 'none';
    popup.style.display = 'none';
  }, 5000);
}

function clearInfo() {
  const fields = ['info-plate', 'info-rfid', 'info-owner', 'info-vehicle', 'info-color', 'info-time', 'info-date', 'info-owner-type', 'info-match-status'];
  fields.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = '-';
  });

  document.getElementById('clear-action').style.display = 'grid';
  document.getElementById('unauth-actions').style.display = 'none';
  document.getElementById('workflow-status').style.display = 'none';
  workflowActive = false;
}

async function clearRfid() {
  try {
    const response = await fetch('/api/clear_rfid', { method: 'POST' });
    if (response.ok) {
      currentRfidData = null;
      clearInfo();
      console.log('RFID data cleared');
    }
  } catch (error) {
    console.error('Error clearing RFID:', error);
  }
}

// Removed - replaced with separate update functions

function updateVehicleInfo(data) {
  if (!data || Object.keys(data).length === 0) return;

  // Check for RFID match
  const rfidMatch = data.rfid_match || {};
  const matchStatus = rfidMatch.match ? 'MATCHED' : (rfidMatch.reason || 'NO MATCH');

  // Show popup for new vehicle entry only if RFID matches
  if (rfidMatch.match) {
    showVehicleEntryPopup(data);
    updateWorkflowStep('step-match', 'completed', 'Match verified');
  } else if (currentRfidData) {
    updateWorkflowStep('step-match', 'error', `Mismatch: ${rfidMatch.message || 'Plates do not match'}`);
  }

  // Update sidebar with vehicle info
  document.getElementById('info-plate').textContent = data.plate || 'Detecting...';
  document.getElementById('info-rfid').textContent = data.rfid || 'N/A';
  document.getElementById('info-owner').textContent = data.owner || 'Unknown';
  document.getElementById('info-vehicle').textContent = data.vehicle || 'Unknown';
  document.getElementById('info-color').textContent = data.color || 'Unknown';
  document.getElementById('info-time').textContent = data.timestamp || data.time || '-';
  document.getElementById('info-date').textContent = data.date || '-';
  document.getElementById('info-match-status').textContent = matchStatus;

  const ownerType = data.role || data.ownerType || 'visitor';
  document.getElementById('info-owner-type').textContent = ownerType;

  const isUnauthorized = !data.owner || data.owner === 'Unknown' || ownerType === 'visitor' || ownerType === 'unknown';

  if (isUnauthorized && !rfidMatch.match) {
    document.getElementById('clear-action').style.display = 'none';
    document.getElementById('unauth-actions').style.display = 'grid';
  } else {
    document.getElementById('clear-action').style.display = 'grid';
    document.getElementById('unauth-actions').style.display = 'none';
  }
}

function updateParkingStatus(data) {
  const total = data.total_capacity || 200;
  const available = data.current_available || 200;
  const occupied = data.occupied || 0;
  const percentage = data.occupancy_rate || 0;

  document.getElementById('total-capacity').textContent = total;
  document.getElementById('occupied').textContent = occupied;
  document.getElementById('available').textContent = available;
  document.getElementById('occupancy-percent').textContent = percentage.toFixed(1) + '%';

  const progressBar = document.querySelector('.occupancy-bar .progress-bar-inner');
  if (progressBar) progressBar.style.width = percentage + '%';
}

function updateVehicleCounts(data) {
  document.getElementById('count-2-wheeler').textContent = data['2_wheeler'] || 0;
  document.getElementById('count-3-wheeler').textContent = data['3_wheeler'] || 0;
  document.getElementById('count-4-wheeler').textContent = data['4_wheeler'] || 0;
  document.getElementById('count-6-wheeler').textContent = data['6_wheeler'] || 0;
}

function updateAllocations(data) {
  const studentCurrent = data.students?.current || 0;
  const studentMax = data.students?.max || 20;
  const studentPercent = studentMax > 0 ? (studentCurrent / studentMax) * 100 : 0;

  document.getElementById('student-count').textContent = `${studentCurrent} / ${studentMax}`;
  const studentBar = document.querySelector('.allocation-item:nth-child(1) .progress-bar-inner');
  if (studentBar) studentBar.style.width = studentPercent + '%';

  const facultyCurrent = data.faculty?.current || 0;
  const facultyMax = data.faculty?.max || 160;
  const facultyPercent = facultyMax > 0 ? (facultyCurrent / facultyMax) * 100 : 0;

  document.getElementById('faculty-count').textContent = `${facultyCurrent} / ${facultyMax}`;
  const facultyBar = document.querySelector('.allocation-item:nth-child(2) .progress-bar-inner');
  if (facultyBar) facultyBar.style.width = facultyPercent + '%';

  const staffCurrent = data.staff?.current || 0;
  const staffMax = data.staff?.max || 30;
  const staffPercent = staffMax > 0 ? (staffCurrent / staffMax) * 100 : 0;

  document.getElementById('staff-count').textContent = `${staffCurrent} / ${staffMax}`;
  const staffBar = document.querySelector('.allocation-item:nth-child(3) .progress-bar-inner');
  if (staffBar) staffBar.style.width = staffPercent + '%';

  const guestCurrent = data.guests?.current || 0;
  const guestMax = data.guests?.max || 20;
  const guestPercent = guestMax > 0 ? (guestCurrent / guestMax) * 100 : 0;

  document.getElementById('guest-count').textContent = `${guestCurrent} / ${guestMax}`;
  const guestBar = document.querySelector('.allocation-item:nth-child(4) .progress-bar-inner');
  if (guestBar) guestBar.style.width = guestPercent + '%';
}

function confirmLogout() {
  if (confirm('Are you sure you want to log out?')) {
    window.location.href = '/logout';
  }
}

function initializeVideoFeed() {
  const videoFeed = document.getElementById('video-feed');
  if (!videoFeed) return;

  videoFeed.onerror = showCameraError;
  videoFeed.onload = showCameraActive;

  fetch('/api/start_camera')
    .then(response => response.json())
    .then(data => {
      if (!data.success) showCameraError();
    })
    .catch(showCameraError);
}

function showCameraError() {
  const videoFeed = document.getElementById('video-feed');
  const cameraStatus = document.querySelector('.camera-status');

  if (videoFeed) videoFeed.style.display = 'none';

  if (cameraStatus) {
    cameraStatus.innerHTML = `<span class="status-indicator" style="background-color: #dc3545;"></span><span>Camera Offline</span>`;
  }
}

function showCameraActive() {
  const videoFeed = document.getElementById('video-feed');
  const cameraStatus = document.querySelector('.camera-status');

  if (videoFeed) videoFeed.style.display = 'block';

  if (cameraStatus) {
    cameraStatus.innerHTML = `<span class="status-indicator active"></span><span>ANPR Active - Live Feed</span>`;
  }
}

function retryCamera() {
  const videoFeed = document.getElementById('video-feed');
  if (videoFeed) {
    videoFeed.src = '/video_feed?' + new Date().getTime();
  }

  fetch('/api/start_camera')
    .then(response => response.json())
    .then(data => {
      if (data.success) showCameraActive();
    })
    .catch(() => console.error('Failed to restart camera'));
}

function updateRfidStatus(isActive, rfidData) {
  const indicator = document.getElementById('rfid-indicator');
  const statusContainer = document.getElementById('rfid-status');

  if (isActive) {
    indicator.className = 'status-indicator active';
    if (statusContainer) {
      statusContainer.innerHTML = '<div class="status-indicator active"></div><span>RFID Scanner: Active</span>';
    }
  } else {
    indicator.className = 'status-indicator';
    if (statusContainer) {
      statusContainer.innerHTML = '<div class="status-indicator"></div><span>RFID Scanner: Inactive</span>';
    }
  }

  // Handle RFID data changes
  if (rfidData && JSON.stringify(rfidData) !== JSON.stringify(currentRfidData)) {
    currentRfidData = rfidData;
    handleRfidDetection(rfidData);
  }
}

function handleRfidDetection(rfidData) {
  if (rfidData.status === 'waiting_for_plate') {
    // Start workflow
    workflowActive = true;
    document.getElementById('workflow-status').style.display = 'block';

    // Update workflow steps
    updateWorkflowStep('step-rfid', 'completed', `RFID scanned: ${rfidData.plate}`);
    updateWorkflowStep('step-camera', 'active', 'Waiting for camera scan...');
    updateWorkflowStep('step-match', 'waiting', 'Waiting...');

    // Pre-fill some info from RFID
    document.getElementById('info-rfid').textContent = rfidData.rfid_code.substring(0, 12) + '...';
    document.getElementById('info-owner').textContent = rfidData.owner;
    document.getElementById('info-vehicle').textContent = rfidData.vehicle;
    document.getElementById('info-color').textContent = rfidData.color;
    document.getElementById('info-owner-type').textContent = rfidData.owner_type;
  }
}

function updateWorkflowStep(stepId, status, text) {
  const step = document.getElementById(stepId);
  if (!step) return;

  const textEl = step.querySelector('.step-text');

  // Remove all status classes
  step.classList.remove('active', 'completed', 'error', 'waiting');

  // Add new status
  step.classList.add(status);
  textEl.textContent = text;
}

function showDenyNotification() {
  console.log('Deny entry clicked');

  // Clear sidebar and RFID data
  clearInfo();
  clearRfid();

  const popup = document.getElementById('notification-popup');
  const backdrop = document.getElementById('denied-entry-backdrop');

  if (popup && backdrop) {
    backdrop.style.display = 'block';
    popup.style.display = 'block';

    setTimeout(() => {
      backdrop.style.display = 'none';
      popup.style.display = 'none';
    }, 3000);
  } else {
    alert('Entry Denied Successfully');
  }
}
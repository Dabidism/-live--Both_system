// Update intervals
const STATS_UPDATE_INTERVAL = 10000; // 10 seconds for stats only
const EVENT_CHECK_INTERVAL = 2000; // 2 seconds for event polling

let isUpdating = false;
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

  // Close modal logic
  const allModals = document.querySelectorAll('.modal-overlay');
  allModals.forEach((modal) => {
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.onclick = () => closeModal(modal);
    modal.onclick = (event) => {
      if (event.target === modal) closeModal(modal);
    };
  });

  // Clear button
  const clearBtn = document.getElementById('clear-btn');
  if (clearBtn) clearBtn.onclick = clearInfo;

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

  async function checkForEvents() {
    try {
      const response = await fetch('/api/latest_event');
      if (response.ok) {
        const data = await response.json();
        const event = data.event;

        // Only show popup if this is a new event and it's an exit
        if (event && event.id !== lastShownEvent && event.event_type === 'exit') {
          // Show popup for exit event
          showVehicleExitPopup(event.event_data);

          // Update sidebar with vehicle info
          updateVehicleInfo(event.event_data);

          // Mark event as handled
          await acknowledgeEvent(event.id);

          // Update last shown event
          lastShownEvent = event.id;
        }
      }
    } catch (error) {
      console.error('Event check error:', error);
    }
    setTimeout(checkForEvents, EVENT_CHECK_INTERVAL);
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
  checkForEvents();
  initializeVideoFeed();
});

function showVehicleExitPopup(data) {
  const popup = document.getElementById('vehicle-exit-popup');
  const backdrop = document.getElementById('vehicle-exit-backdrop');

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
  const fields = ['info-plate', 'info-owner', 'info-vehicle', 'info-color', 'info-time', 'info-date', 'info-owner-type', 'info-status'];
  fields.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = '-';
  });

  document.getElementById('clear-action').style.display = 'grid';
}

function updateVehicleInfo(data) {
  if (!data || Object.keys(data).length === 0) return;

  // Update sidebar with vehicle info (popup is handled by event system)
  document.getElementById('info-plate').textContent = data.plate || 'Detecting...';
  document.getElementById('info-owner').textContent = data.owner || 'Unknown';
  document.getElementById('info-vehicle').textContent = data.vehicle || 'Unknown';
  document.getElementById('info-color').textContent = data.color || 'Unknown';
  document.getElementById('info-time').textContent = data.timestamp || data.time || '-';
  document.getElementById('info-date').textContent = data.date || '-';
  document.getElementById('info-owner-type').textContent = data.role || data.ownerType || 'visitor';
  document.getElementById('info-status').textContent = 'EXITED';

  document.getElementById('clear-action').style.display = 'grid';
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
  document.getElementById('count-4-wheeler').textContent = data['4_wheeler'] || 0;
  document.getElementById('count-other').textContent = data['other'] || 0;
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
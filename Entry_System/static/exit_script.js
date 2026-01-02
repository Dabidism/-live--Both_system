// Update intervals
const STATS_UPDATE_INTERVAL = 10000; // 10 seconds for stats only
const VEHICLE_CHECK_INTERVAL = 3000; // 3 seconds for vehicle info

let isUpdating = false;
let lastVehicleData = null;

document.addEventListener('DOMContentLoaded', function () {
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
        
        // Only update if vehicle data changed and it's an exit
        if (JSON.stringify(vehicleData) !== JSON.stringify(lastVehicleData) && vehicleData.action === 'EXITED') {
          updateVehicleInfo(vehicleData);
          lastVehicleData = vehicleData;
        }
      }
    } catch (error) {
      console.error('Vehicle check error:', error);
    }
    setTimeout(checkVehicleInfo, VEHICLE_CHECK_INTERVAL);
  }
  
  clearInfo();
  updateStats();
  checkVehicleInfo();
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
}

function updateVehicleInfo(data) {
  if (!data || Object.keys(data).length === 0) return;

  // Show popup for vehicle exit
  showVehicleExitPopup(data);

  // Update sidebar with vehicle info
  document.getElementById('info-plate').textContent = data.plate || 'Detecting...';
  document.getElementById('info-owner').textContent = data.owner || 'Unknown';
  document.getElementById('info-vehicle').textContent = data.vehicle || 'Unknown';
  document.getElementById('info-color').textContent = data.color || 'Unknown';
  document.getElementById('info-time').textContent = data.timestamp || data.time || '-';
  document.getElementById('info-date').textContent = data.date || '-';
  document.getElementById('info-owner-type').textContent = data.role || data.ownerType || 'visitor';
  document.getElementById('info-status').textContent = 'EXITED';
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
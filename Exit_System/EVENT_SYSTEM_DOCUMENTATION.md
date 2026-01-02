# Event Handling System Documentation

## Overview
This document explains the new event handling system that fixes the popup reappearing issue after page refresh.

## Problem Solved
- **Before**: Popups would reappear every time the page was refreshed because the backend kept returning the same vehicle data
- **After**: Popups only show for NEW vehicle events and never repeat after page refresh

## System Architecture

### Database Schema

#### New Table: `vehicle_events`
```sql
CREATE TABLE vehicle_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plate_num VARCHAR(20) NOT NULL,
    event_type ENUM('entry', 'exit') NOT NULL,
    event_data JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    handled TINYINT DEFAULT 0,
    INDEX idx_handled_timestamp (handled, timestamp),
    INDEX idx_plate_timestamp (plate_num, timestamp)
);
```

#### Updated Table: `historical_log`
- Added `exitTime TIMESTAMP NULL` column
- Status now updates to 'exit' instead of moving records to `entryexitlog`

### Backend Components

#### 1. Event Model (`app/models/event.py`)
- `VehicleEvent` dataclass for event representation
- Includes `handled` flag to track event processing

#### 2. Event Queries (`app/database/event_queries.py`)
- `create_event()`: Creates new vehicle events
- `get_latest_unhandled_event()`: Returns only unhandled events
- `mark_event_handled()`: Marks events as processed
- `cleanup_old_events()`: Removes old events

#### 3. Updated ANPR Service (`app/services/anpr_service.py`)
- Creates events when vehicles enter/exit
- Events contain complete vehicle information
- Separate events for entry and exit systems

#### 4. New API Endpoints (`app/controllers/web_controller.py`)

##### `/api/latest_event`
- Returns only events where `handled = 0`
- Returns `{"event": null}` if no unhandled events
- Never returns already processed events

##### `/api/ack_event`
- Accepts event ID via POST
- Sets `handled = 1` for that event
- Prevents event from being returned again

### Frontend Components

#### Updated JavaScript Files
- `static/script.js` (Entry system)
- `static/exit_script.js` (Exit system)

#### Key Changes
1. **Event Polling**: Polls `/api/latest_event` every 2 seconds
2. **Event Tracking**: Tracks `lastShownEvent` ID to prevent duplicates
3. **Acknowledgment**: Calls `/api/ack_event` after showing popup
4. **System-Specific**: Entry system shows entry events, exit system shows exit events

## Event Flow

### Entry System Flow
1. Vehicle detected by ANPR → Event created with `event_type = 'entry'`
2. Frontend polls `/api/latest_event`
3. If new entry event found → Show entry popup
4. Frontend calls `/api/ack_event` → Event marked as handled
5. Event never returned again

### Exit System Flow
1. Vehicle detected by ANPR → Event created with `event_type = 'exit'`
2. Frontend polls `/api/latest_event`
3. If new exit event found → Show exit popup
4. Frontend calls `/api/ack_event` → Event marked as handled
5. Historical log updated with `status = 'exit'` and `exitTime`

## Key Features

### ✅ No Duplicate Popups
- Events are marked as handled after being shown
- `lastShownEvent` tracking prevents client-side duplicates

### ✅ Refresh-Safe
- Page refresh never shows old events
- Only unhandled events are returned by API

### ✅ System Separation
- Entry system only shows entry events
- Exit system only shows exit events

### ✅ Data Persistence
- Vehicle exit updates historical_log status
- Complete audit trail maintained

### ✅ Performance Optimized
- Efficient database queries with indexes
- Automatic cleanup of old events
- Minimal polling overhead

## Configuration

### Polling Intervals
```javascript
const EVENT_CHECK_INTERVAL = 2000; // 2 seconds for event polling
const STATS_UPDATE_INTERVAL = 10000; // 10 seconds for stats
```

### Database Cleanup
- Old events automatically cleaned up after 7 days
- Configurable via `cleanup_old_events(days=7)`

## Testing Scenarios

### ✅ Normal Operation
1. Vehicle enters → Popup shows once
2. Page refresh → No popup
3. Another vehicle enters → New popup shows

### ✅ Multiple Users
1. User A sees popup for vehicle entry
2. User B refreshes page → No popup
3. New vehicle → Both users see popup

### ✅ System Restart
1. Server restarts
2. Page refresh → No old popups
3. New vehicles → Popups work normally

## Maintenance

### Database Maintenance
```sql
-- Manual cleanup of old events
DELETE FROM vehicle_events WHERE timestamp < DATE_SUB(NOW(), INTERVAL 7 DAY);

-- Check unhandled events
SELECT * FROM vehicle_events WHERE handled = 0;

-- Reset event handling (for testing)
UPDATE vehicle_events SET handled = 0 WHERE id = ?;
```

### Monitoring
- Monitor `vehicle_events` table size
- Check for stuck unhandled events
- Verify event creation during vehicle detection

## Migration Notes

### From Old System
1. Run `init_event_table.sql` to create required tables
2. Deploy updated code
3. Old vehicle_info polling is replaced with event polling
4. No data migration needed - system starts fresh

### Rollback Plan
1. Revert to old JavaScript files
2. Remove event table (optional)
3. Old system will resume working

## Performance Impact

### Positive
- Reduced unnecessary API calls
- Better user experience
- Cleaner data flow

### Minimal Overhead
- Small event table with efficient indexes
- JSON storage for flexible event data
- Automatic cleanup prevents growth

## Security Considerations

### Authentication
- All event endpoints require guard session
- Event data contains no sensitive information

### Data Validation
- Event IDs validated before acknowledgment
- JSON event data sanitized

## Future Enhancements

### Possible Additions
1. Event categories (violation, maintenance, etc.)
2. Event priority levels
3. Real-time WebSocket notifications
4. Event analytics and reporting

### Scalability
- Current design supports multiple concurrent users
- Database indexes optimize for high-frequency polling
- Event cleanup prevents unbounded growth
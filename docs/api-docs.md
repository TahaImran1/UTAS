# UTAS API Documentation

The UTAS server provides the following endpoints for device communication and data visualization.

## 1. Device Communication (ADMS/Push)

### Heartbeat / Check
- **Endpoint**: `GET /iclock/cdata`
- **Description**: Used by the ZKTeco device to check server availability.
- **Response**: `OK`

### Data Upload (Attendance Logs)
- **Endpoint**: `POST /iclock/cdata`
- **Query Params**: `SN` (Device serial number), `table=ATTLOG`
- **Description**: Receives real-time attendance logs from the device.
- **Response**: `OK`

### Command Polling
- **Endpoint**: `GET /iclock/getrequest`
- **Description**: The device polls this endpoint for any pending commands from the server.
- **Response**: `OK`

## 2. Web Viewer

### Live Logs Viewer
- **Endpoint**: `GET /view`
- **Description**: An HTML page showing the most recent 100 logs received from connected devices.
- **Auto-Refresh**: 5 seconds.

### API Specifications (Swagger)
- **Endpoint**: `/docs`
- **Description**: Interactive OpenAPI documentation for testing endpoints.

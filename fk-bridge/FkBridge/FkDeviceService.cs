using System.Runtime.InteropServices;
using System.Collections.Concurrent;
using Microsoft.Extensions.Options;

namespace FkBridge;

public sealed class FkBridgeOptions
{
    public int DefaultPort { get; set; } = 5005;
    public int DefaultTimeoutMs { get; set; } = 5000;
    public int DefaultMachineNo { get; set; } = 1;
    public int DefaultLicense { get; set; } = 1263;
    public int DefaultNetPassword { get; set; } = 0;
}

public sealed class FkDeviceService
{
    private readonly FkBridgeOptions _defaults;
    private readonly ConcurrentDictionary<string, int> _handles = new();
    private readonly ConcurrentDictionary<string, object> _locks = new();

    public FkDeviceService(IOptions<FkBridgeOptions> options)
    {
        _defaults = options.Value;
    }

    public static bool DllPresent()
    {
        try
        {
            return NativeLibrary.TryLoad("FKAttend.dll", out _);
        }
        catch
        {
            return false;
        }
    }

    private static string Key(DeviceRequest r) => $"{r.Ip}:{r.Port ?? 5005}";

    private object LockFor(string key) => _locks.GetOrAdd(key, _ => new object());

    private void Resolve(DeviceRequest r, out int port, out int machineNo, out int license,
        out int timeoutMs, out int netPassword)
    {
        port = r.Port ?? _defaults.DefaultPort;
        machineNo = r.MachineNo ?? _defaults.DefaultMachineNo;
        license = r.License ?? _defaults.DefaultLicense;
        timeoutMs = r.TimeoutMs ?? _defaults.DefaultTimeoutMs;
        netPassword = r.NetPassword ?? _defaults.DefaultNetPassword;
    }

    public static string ErrorText(int code) => code switch
    {
        (int)FkErrorCode.RunSuccess => "OK",
        (int)FkErrorCode.RunErrNoOpenComm => "No open connection",
        (int)FkErrorCode.RunErrMisPassword => "License error",
        (int)FkErrorCode.RunErrDataArrayEnd => "End of data",
        _ => $"FK error {code}"
    };

    public (bool ok, int handle, string? error) Connect(DeviceRequest req)
    {
        Resolve(req, out var port, out var machineNo, out var license, out var timeoutMs, out var netPassword);
        var handle = FkAttendNative.FK_ConnectNet(
            machineNo, req.Ip, port, timeoutMs,
            (int)FkProtocolType.TcpIp, netPassword, license);

        if (handle <= 0)
            return (false, handle, ErrorText(handle));

        return (true, handle, null);
    }

    public void Disconnect(DeviceRequest req)
    {
    }

    private static bool Enable(int handle, byte flag, out string? error)
    {
        var rc = FkAttendNative.FK_EnableDevice(handle, flag);
        if (rc == (int)FkErrorCode.RunSuccess) { error = null; return true; }
        error = ErrorText(rc);
        return false;
    }

    public (bool ok, List<AttendanceLogDto> logs, string? error) Pull(DeviceRequest req)
    {
        var key = Key(req);
        lock (LockFor(key))
        {
            var (ok, handle, error) = Connect(req);
            if (!ok) return (false, new(), error);

            try
            {
                if (!Enable(handle, 0, out error)) return (false, new(), error);

                try
                {
                    var readMark = req.ReadMark ?? 0;
                    var loadRc = FkAttendNative.FK_LoadGeneralLogData(handle, readMark);
                    if (loadRc != (int)FkErrorCode.RunSuccess)
                        return (false, new(), ErrorText(loadRc));

                    var logs = new List<AttendanceLogDto>();
                    while (true)
                    {
                        int enroll = 0, verify = 0, io = 0;
                        var dt = DateTime.MinValue;
                        var rc = FkAttendNative.FK_GetGeneralLogData(handle, ref enroll, ref verify, ref io, ref dt);
                        if (rc == (int)FkErrorCode.RunErrDataArrayEnd) break;
                        if (rc != (int)FkErrorCode.RunSuccess)
                            return (false, logs, ErrorText(rc));

                        logs.Add(new AttendanceLogDto
                        {
                            UserId = enroll.ToString(),
                            Timestamp = dt.ToString("yyyy-MM-dd HH:mm:ss"),
                            VerifyMode = verify,
                            InOutMode = io
                        });
                    }
                    return (true, logs, null);
                }
                finally
                {
                    Enable(handle, 1, out _);
                }
            }
            finally
            {
                FkAttendNative.FK_DisConnect(handle);
            }
        }
    }

    public (bool ok, string? error) Clear(DeviceRequest req)
    {
        var key = Key(req);
        lock (LockFor(key))
        {
            var (ok, handle, error) = Connect(req);
            if (!ok) return (false, error);

            try
            {
                if (!Enable(handle, 0, out error)) return (false, error);
                try
                {
                    var rc = FkAttendNative.FK_EmptyGeneralLogData(handle);
                    return (rc == (int)FkErrorCode.RunSuccess, rc == (int)FkErrorCode.RunSuccess ? null : ErrorText(rc));
                }
                finally { Enable(handle, 1, out _); }
            }
            finally
            {
                FkAttendNative.FK_DisConnect(handle);
            }
        }
    }

    public (bool ok, Dictionary<string, object?> info, string? error) GetInfo(DeviceRequest req)
    {
        var key = Key(req);
        lock (LockFor(key))
        {
            var (ok, handle, error) = Connect(req);
            if (!ok) return (false, new(), error);

            try
            {
                var info = new Dictionary<string, object?>();
                var dt = DateTime.Now;
                if (FkAttendNative.FK_GetDeviceTime(handle, ref dt) == (int)FkErrorCode.RunSuccess)
                    info["device_time"] = dt.ToString("yyyy-MM-dd HH:mm:ss");

                string serial = new(' ', 256);
                if (FkAttendNative.FK_GetProductData(handle, (int)FkProductInfo.SerialNumber, ref serial)
                    == (int)FkErrorCode.RunSuccess)
                    info["serial_number"] = serial.Trim();

                string product = new(' ', 256);
                if (FkAttendNative.FK_GetProductData(handle, (int)FkProductInfo.ProductName, ref product)
                    == (int)FkErrorCode.RunSuccess)
                    info["product_name"] = product.Trim();

                info["ip"] = req.Ip;
                Resolve(req, out int port, out int machineNo, out int license, out int timeoutMs, out int netPassword);
                info["port"] = port;
                return (true, info, null);
            }
            finally
            {
                FkAttendNative.FK_DisConnect(handle);
            }
        }
    }

    public (bool ok, string? error) SyncTime(DeviceRequest req)
    {
        var key = Key(req);
        lock (LockFor(key))
        {
            var (ok, handle, error) = Connect(req);
            if (!ok) return (false, error);

            try
            {
                if (!Enable(handle, 0, out error)) return (false, error);
                try
                {
                    var rc = FkAttendNative.FK_SetDeviceTime(handle, DateTime.Now);
                    return (rc == (int)FkErrorCode.RunSuccess, rc == (int)FkErrorCode.RunSuccess ? null : ErrorText(rc));
                }
                finally { Enable(handle, 1, out _); }
            }
            finally
            {
                FkAttendNative.FK_DisConnect(handle);
            }
        }
    }
}




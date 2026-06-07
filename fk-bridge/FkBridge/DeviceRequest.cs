namespace FkBridge;

public sealed class DeviceRequest
{
    public string Ip { get; set; } = "";
    public int? Port { get; set; }
    public int? MachineNo { get; set; }
    public int? License { get; set; }
    public int? TimeoutMs { get; set; }
    public int? NetPassword { get; set; }
    public int? ReadMark { get; set; }
}

public sealed class AttendanceLogDto
{
    public string UserId { get; set; } = "";
    public string Timestamp { get; set; } = "";
    public int VerifyMode { get; set; }
    public int InOutMode { get; set; }
}

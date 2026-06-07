using FkBridge;

var builder = WebApplication.CreateBuilder(args);
builder.Services.Configure<FkBridgeOptions>(builder.Configuration.GetSection("FkBridge"));
builder.Services.AddSingleton<FkDeviceService>();

var app = builder.Build();

app.MapGet("/health", () => Results.Json(new
{
    status = "ok",
    dll_loaded = FkDeviceService.DllPresent()
}));

app.MapPost("/connect", (DeviceRequest req, FkDeviceService svc) =>
{
    if (string.IsNullOrWhiteSpace(req.Ip))
        return Results.BadRequest(new { success = false, error = "ip required" });
    var (ok, handle, error) = svc.Connect(req);
    return Results.Json(new { success = ok, handle, error });
});

app.MapPost("/disconnect", (DeviceRequest req, FkDeviceService svc) =>
{
    svc.Disconnect(req);
    return Results.Json(new { success = true });
});

app.MapPost("/pull", (DeviceRequest req, FkDeviceService svc) =>
{
    if (string.IsNullOrWhiteSpace(req.Ip))
        return Results.BadRequest(new { success = false, error = "ip required" });
    var (ok, logs, error) = svc.Pull(req);
    return Results.Json(new { success = ok, logs, count = logs.Count, error });
});

app.MapPost("/clear", (DeviceRequest req, FkDeviceService svc) =>
{
    var (ok, error) = svc.Clear(req);
    return Results.Json(new { success = ok, error });
});

app.MapGet("/info", (string ip, int? port, int? machine_no, int? license, int? timeout_ms, int? net_password, FkDeviceService svc) =>
{
    var req = new DeviceRequest { Ip = ip, Port = port, MachineNo = machine_no, License = license, TimeoutMs = timeout_ms, NetPassword = net_password };
    var (ok, info, error) = svc.GetInfo(req);
    return Results.Json(new { success = ok, info, error });
});

app.MapPost("/sync_time", (DeviceRequest req, FkDeviceService svc) =>
{
    var (ok, error) = svc.SyncTime(req);
    return Results.Json(new { success = ok, synced_to = DateTime.Now.ToString("o"), error });
});

app.Run();

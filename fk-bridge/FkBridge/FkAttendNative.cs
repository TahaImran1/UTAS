using System.Runtime.InteropServices;

namespace FkBridge;

public static class FkAttendNative
{
    private const string DllName = "FKAttend.dll";

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_ConnectNet(int anMachineNo, string astrIpAddress, int anNetPort,
        int anTimeOut, int anProtocolType, int anNetPassword, int anLicense);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern void FK_DisConnect(int anHandleIndex);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_EnableDevice(int anHandleIndex, byte anEnableFlag);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_GetDeviceTime(int anHandleIndex, ref DateTime apnDateTime);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_SetDeviceTime(int anHandleIndex, DateTime anDateTime);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_GetProductData(int anHandleIndex, int anDataIndex,
        [MarshalAs(UnmanagedType.LPStr)] ref string apstrValue);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_LoadGeneralLogData(int anHandleIndex, int anReadMark);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_GetGeneralLogData(int anHandleIndex, ref int apnEnrollNumber,
        ref int apnVerifyMode, ref int apnInOutMode, ref DateTime apnDateTime);

    [DllImport(DllName, CharSet = CharSet.Ansi)]
    public static extern int FK_EmptyGeneralLogData(int anHandleIndex);
}

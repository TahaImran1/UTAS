namespace FkBridge;

public enum FkErrorCode
{
    RunSuccess = 1,
    RunErrNoSupport = 0,
    RunErrUnknownError = -1,
    RunErrNoOpenComm = -2,
    RunErrWriteFail = -3,
    RunErrReadFail = -4,
    RunErrInvalidParam = -5,
    RunErrNonCarryout = -6,
    RunErrDataArrayEnd = -7,
    RunErrDataArrayNone = -8,
    RunErrMemory = -9,
    RunErrMisPassword = -10,
}

public enum FkProtocolType
{
    TcpIp = 0,
    Udp = 1,
}
public enum FkProductInfo
{
    SerialNumber = 1,
    ProductCode = 3,
    ProductName = 4,
}


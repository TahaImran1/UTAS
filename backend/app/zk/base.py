# -*- coding: utf-8 -*-
import sys
from datetime import datetime
from socket import AF_INET, SOCK_DGRAM, SOCK_STREAM, socket, timeout
from struct import pack, unpack
import codecs

# Fixed: all imports are now relative (package-style)
from . import const
from .attendance import Attendance
from .exception import ZKErrorConnection, ZKErrorResponse, ZKNetworkError
from .user import User
from .finger import Finger


def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default


def make_commkey(key, session_id, ticks=50):
    """
    take a password and session_id and scramble them to send to the machine.
    copied from commpro.c - MakeKey
    """
    key = int(key)
    session_id = int(session_id)
    k = 0
    for i in range(32):
        if (key & (1 << i)):
            k = (k << 1 | 1)
        else:
            k = k << 1
    k += session_id

    k = pack(b'I', k)
    k = unpack(b'BBBB', k)
    k = pack(
        b'BBBB',
        k[0] ^ ord('Z'),
        k[1] ^ ord('K'),
        k[2] ^ ord('S'),
        k[3] ^ ord('O'))
    k = unpack(b'HH', k)
    k = pack(b'HH', k[1], k[0])

    B = 0xff & ticks
    k = unpack(b'BBBB', k)
    k = pack(
        b'BBBB',
        k[0] ^ B,
        k[1] ^ B,
        B,
        k[3] ^ B)
    return k


class ZK_helper(object):
    """ZK helper class"""

    def __init__(self, ip, port=4370):
        self.address = (ip, port)
        self.ip = ip
        self.port = port

    def test_ping(self):
        import subprocess, platform
        ping_str = "-n 1" if platform.system().lower() == "windows" else "-c 1 -W 5"
        args = "ping " + " " + ping_str + " " + self.ip
        need_sh = False if platform.system().lower() == "windows" else True
        return subprocess.call(args,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               shell=need_sh) == 0

    def test_tcp(self):
        self.client = socket(AF_INET, SOCK_STREAM)
        self.client.settimeout(10)
        res = self.client.connect_ex(self.address)
        self.client.close()
        return res

    def test_udp(self):
        self.client = socket(AF_INET, SOCK_DGRAM)
        self.client.settimeout(10)


class ZK(object):
    """ZK main class"""

    def __init__(self, ip, port=4370, timeout=60, password=0, force_udp=False,
                 ommit_ping=False, verbose=False, encoding='UTF-8'):
        User.encoding = encoding
        self.__address = (ip, port)
        self.__sock = socket(AF_INET, SOCK_DGRAM)
        self.__sock.settimeout(timeout)
        self.__timeout = timeout
        self.__password = password
        self.__session_id = 0
        self.__reply_id = const.USHRT_MAX - 1
        self.__data_recv = None
        self.__data = None

        self.is_connect = False
        self.is_enabled = True
        self.helper = ZK_helper(ip, port)
        self.force_udp = force_udp
        self.ommit_ping = ommit_ping
        self.verbose = verbose
        self.encoding = encoding
        self.tcp = not force_udp
        self.users = 0
        self.fingers = 0
        self.records = 0
        self.dummy = 0
        self.cards = 0
        self.fingers_cap = 0
        self.users_cap = 0
        self.rec_cap = 0
        self.faces = 0
        self.faces_cap = 0
        self.fingers_av = 0
        self.users_av = 0
        self.rec_av = 0
        self.next_uid = 1
        self.next_user_id = '1'
        self.user_packet_size = 28
        self.end_live_capture = False

    def __nonzero__(self):
        return self.is_connect

    def __create_socket(self):
        if self.tcp:
            self.__sock = socket(AF_INET, SOCK_STREAM)
            self.__sock.settimeout(self.__timeout)
            self.__sock.connect_ex(self.__address)
        else:
            self.__sock = socket(AF_INET, SOCK_DGRAM)
            self.__sock.settimeout(self.__timeout)

    def __create_tcp_top(self, packet):
        length = len(packet)
        top = pack('<HHI', const.MACHINE_PREPARE_DATA_1, const.MACHINE_PREPARE_DATA_2, length)
        return top + packet

    def __create_header(self, command, command_string, session_id, reply_id):
        buf = pack('<4H', command, 0, session_id, reply_id) + command_string
        buf = unpack('8B' + '%sB' % len(command_string), buf)
        checksum = unpack('H', self.__create_checksum(buf))[0]
        reply_id += 1
        if reply_id >= const.USHRT_MAX:
            reply_id -= const.USHRT_MAX
        buf = pack('<4H', command, checksum, session_id, reply_id)
        return buf + command_string

    def __create_checksum(self, p):
        l = len(p)
        checksum = 0
        while l > 1:
            checksum += unpack('H', pack('BB', p[0], p[1]))[0]
            p = p[2:]
            if checksum > const.USHRT_MAX:
                checksum -= const.USHRT_MAX
            l -= 2
        if l:
            checksum = checksum + p[-1]
        while checksum > const.USHRT_MAX:
            checksum -= const.USHRT_MAX
        checksum = ~checksum
        while checksum < 0:
            checksum += const.USHRT_MAX
        return pack('H', checksum)

    def __test_tcp_top(self, packet):
        if len(packet) <= 8:
            return 0
        tcp_header = unpack('<HHI', packet[:8])
        if tcp_header[0] == const.MACHINE_PREPARE_DATA_1 and tcp_header[1] == const.MACHINE_PREPARE_DATA_2:
            return tcp_header[2]
        return 0

    def __send_command(self, command, command_string=b'', response_size=8):
        if command not in [const.CMD_CONNECT, const.CMD_AUTH] and not self.is_connect:
            raise ZKErrorConnection("instance are not connected.")

        buf = self.__create_header(command, command_string, self.__session_id, self.__reply_id)
        try:
            if self.tcp:
                top = self.__create_tcp_top(buf)
                self.__sock.send(top)
                self.__tcp_data_recv = self.__sock.recv(response_size + 8)
                self.__tcp_length = self.__test_tcp_top(self.__tcp_data_recv)
                if self.__tcp_length == 0:
                    raise ZKNetworkError("TCP packet invalid")
                self.__header = unpack('<4H', self.__tcp_data_recv[8:16])
                self.__data_recv = self.__tcp_data_recv[8:]
            else:
                self.__sock.sendto(buf, self.__address)
                self.__data_recv = self.__sock.recv(response_size)
                self.__header = unpack('<4H', self.__data_recv[:8])
        except Exception as e:
            raise ZKNetworkError(str(e))

        self.__response = self.__header[0]
        self.__reply_id = self.__header[3]
        self.__data = self.__data_recv[8:]
        if self.__response in [const.CMD_ACK_OK, const.CMD_PREPARE_DATA, const.CMD_DATA]:
            return {'status': True, 'code': self.__response}
        return {'status': False, 'code': self.__response}

    def __ack_ok(self):
        buf = self.__create_header(const.CMD_ACK_OK, b'', self.__session_id, const.USHRT_MAX - 1)
        try:
            if self.tcp:
                top = self.__create_tcp_top(buf)
                self.__sock.send(top)
            else:
                self.__sock.sendto(buf, self.__address)
        except Exception as e:
            raise ZKNetworkError(str(e))

    def __get_data_size(self):
        response = self.__response
        if response == const.CMD_PREPARE_DATA:
            size = unpack('I', self.__data[:4])[0]
            return size
        else:
            return 0

    def __decode_time(self, t):
        t = unpack("<I", t)[0]
        second = t % 60; t = t // 60
        minute = t % 60; t = t // 60
        hour = t % 24; t = t // 24
        day = t % 31 + 1; t = t // 31
        month = t % 12 + 1; t = t // 12
        year = t + 2000
        return datetime(year, month, day, hour, minute, second)

    def __decode_timehex(self, timehex):
        year, month, day, hour, minute, second = unpack("6B", timehex)
        year += 2000
        return datetime(year, month, day, hour, minute, second)

    def __encode_time(self, t):
        d = (
            ((t.year % 100) * 12 * 31 + ((t.month - 1) * 31) + t.day - 1) *
            (24 * 60 * 60) + (t.hour * 60 + t.minute) * 60 + t.second
        )
        return d

    def connect(self):
        self.end_live_capture = False
        if not self.ommit_ping and not self.helper.test_ping():
            raise ZKNetworkError("can't reach device (ping %s)" % self.__address[0])
        if not self.force_udp and self.helper.test_tcp() == 0:
            self.user_packet_size = 72
        self.__create_socket()
        self.__session_id = 0
        self.__reply_id = const.USHRT_MAX - 1
        cmd_response = self.__send_command(const.CMD_CONNECT)
        self.__session_id = self.__header[2]
        if cmd_response.get('code') == const.CMD_ACK_UNAUTH:
            if self.verbose: print("try auth")
            command_string = make_commkey(self.__password, self.__session_id)
            cmd_response = self.__send_command(const.CMD_AUTH, command_string)
        if cmd_response.get('status'):
            self.is_connect = True
            return self
        else:
            if cmd_response["code"] == const.CMD_ACK_UNAUTH:
                raise ZKErrorResponse("Unauthenticated")
            raise ZKErrorResponse("Invalid response: Can't connect")

    def disconnect(self):
        cmd_response = self.__send_command(const.CMD_EXIT)
        if cmd_response.get('status'):
            self.is_connect = False
            if self.__sock:
                self.__sock.close()
            return True
        else:
            raise ZKErrorResponse("can't disconnect")

    def enable_device(self):
        cmd_response = self.__send_command(const.CMD_ENABLEDEVICE)
        if cmd_response.get('status'):
            self.is_enabled = True
            return True
        else:
            raise ZKErrorResponse("Can't enable device")

    def disable_device(self):
        cmd_response = self.__send_command(const.CMD_DISABLEDEVICE)
        if cmd_response.get('status'):
            self.is_enabled = False
            return True
        else:
            raise ZKErrorResponse("Can't disable device")

    def get_firmware_version(self):
        cmd_response = self.__send_command(const.CMD_GET_VERSION, b'', 1024)
        if cmd_response.get('status'):
            return self.__data.split(b'\x00')[0].decode()
        raise ZKErrorResponse("Can't read firmware version")

    def get_serialnumber(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'~SerialNumber\x00', 1024)
        if cmd_response.get('status'):
            serialnumber = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return serialnumber.replace(b'=', b'').decode()
        raise ZKErrorResponse("Can't read serial number")

    def get_platform(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'~Platform\x00', 1024)
        if cmd_response.get('status'):
            platform = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return platform.replace(b'=', b'').decode()
        raise ZKErrorResponse("Can't read platform name")

    def get_mac(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'MAC\x00', 1024)
        if cmd_response.get('status'):
            mac = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return mac.decode()
        raise ZKErrorResponse("can't read mac address")

    def get_device_name(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'~DeviceName\x00', 1024)
        if cmd_response.get('status'):
            device = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return device.decode()
        return ""

    def get_face_version(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'ZKFaceVersion\x00', 1024)
        if cmd_response.get('status'):
            response = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return safe_cast(response, int, 0) if response else 0
        return None

    def get_fp_version(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'~ZKFPVersion\x00', 1024)
        if cmd_response.get('status'):
            response = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return safe_cast(response.replace(b'=', b''), int, 0) if response else 0
        raise ZKErrorResponse("can't read fingerprint version")

    def _clear_error(self, command_string=b''):
        self.__send_command(const.CMD_ACK_ERROR, command_string, 1024)
        self.__send_command(const.CMD_ACK_UNKNOWN, command_string, 1024)
        self.__send_command(const.CMD_ACK_UNKNOWN, command_string, 1024)
        self.__send_command(const.CMD_ACK_UNKNOWN, command_string, 1024)

    def get_extend_fmt(self):
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'~ExtendFmt\x00', 1024)
        if cmd_response.get('status'):
            fmt = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
            return safe_cast(fmt, int, 0) if fmt else 0
        self._clear_error(b'~ExtendFmt\x00')
        return None

    def get_network_params(self):
        ip = self.__address[0]
        mask = b''
        gate = b''
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'IPAddress\x00', 1024)
        if cmd_response.get('status'):
            ip = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'NetMask\x00', 1024)
        if cmd_response.get('status'):
            mask = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
        cmd_response = self.__send_command(const.CMD_OPTIONS_RRQ, b'GATEIPAddress\x00', 1024)
        if cmd_response.get('status'):
            gate = self.__data.split(b'=', 1)[-1].split(b'\x00')[0]
        return {'ip': ip.decode() if isinstance(ip, bytes) else ip,
                'mask': mask.decode() if isinstance(mask, bytes) else mask,
                'gateway': gate.decode() if isinstance(gate, bytes) else gate}

    def free_data(self):
        cmd_response = self.__send_command(const.CMD_FREE_DATA)
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("can't free data")

    def read_sizes(self):
        cmd_response = self.__send_command(const.CMD_GET_FREE_SIZES, b'', 1024)
        if cmd_response.get('status'):
            if len(self.__data) >= 80:
                fields = unpack('20i', self.__data[:80])
                self.users = fields[4]
                self.fingers = fields[6]
                self.records = fields[8]
                self.dummy = fields[10]
                self.cards = fields[12]
                self.fingers_cap = fields[14]
                self.users_cap = fields[15]
                self.rec_cap = fields[16]
                self.fingers_av = fields[17]
                self.users_av = fields[18]
                self.rec_av = fields[19]
                self.__data = self.__data[80:]
            if len(self.__data) >= 12:
                fields = unpack('3i', self.__data[:12])
                self.faces = fields[0]
                self.faces_cap = fields[2]
            return True
        raise ZKErrorResponse("can't read sizes")

    def unlock(self, time=3):
        cmd_response = self.__send_command(const.CMD_UNLOCK, pack("I", int(time) * 10))
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("Can't open door")

    def get_lock_state(self):
        cmd_response = self.__send_command(const.CMD_DOORSTATE_RRQ)
        return bool(cmd_response.get('status'))

    def __str__(self):
        return "ZK %s://%s:%s users[%i]:%i/%i fingers:%i/%i, records:%i/%i faces:%i/%i" % (
            "tcp" if self.tcp else "udp", self.__address[0], self.__address[1],
            self.user_packet_size, self.users, self.users_cap,
            self.fingers, self.fingers_cap,
            self.records, self.rec_cap,
            self.faces, self.faces_cap)

    def restart(self):
        cmd_response = self.__send_command(const.CMD_RESTART)
        if cmd_response.get('status'):
            self.is_connect = False
            self.next_uid = 1
            return True
        raise ZKErrorResponse("can't restart device")

    def get_time(self):
        cmd_response = self.__send_command(const.CMD_GET_TIME, b'', 1032)
        if cmd_response.get('status'):
            return self.__decode_time(self.__data[:4])
        raise ZKErrorResponse("can't get time")

    def set_time(self, timestamp):
        cmd_response = self.__send_command(const.CMD_SET_TIME, pack(b'I', self.__encode_time(timestamp)))
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("can't set time")

    def refresh_data(self):
        cmd_response = self.__send_command(const.CMD_REFRESHDATA)
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("can't refresh data")

    def cancel_capture(self):
        cmd_response = self.__send_command(const.CMD_CANCELCAPTURE)
        return bool(cmd_response.get('status'))

    def verify_user(self):
        cmd_response = self.__send_command(const.CMD_STARTVERIFY)
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("Cant Verify")

    def reg_event(self, flags):
        cmd_response = self.__send_command(const.CMD_REG_EVENT, pack("I", flags))
        if not cmd_response.get('status'):
            raise ZKErrorResponse("cant' reg events %i" % flags)

    def get_users(self):
        self.read_sizes()
        if self.users == 0:
            self.next_uid = 1
            self.next_user_id = '1'
            return []
        users = []
        max_uid = 0
        userdata, size = self.read_with_buffer(const.CMD_USERTEMP_RRQ, const.FCT_USER)
        if size <= 4:
            return []
        total_size = unpack("I", userdata[:4])[0]
        self.user_packet_size = total_size / self.users
        userdata = userdata[4:]
        if self.user_packet_size == 28:
            while len(userdata) >= 28:
                uid, privilege, password, name, card, group_id, timezone, user_id = unpack(
                    '<HB5s8sIxBhI', userdata.ljust(28, b'\x00')[:28])
                if uid > max_uid: max_uid = uid
                password = (password.split(b'\x00')[0]).decode(self.encoding, errors='ignore')
                name = (name.split(b'\x00')[0]).decode(self.encoding, errors='ignore').strip()
                if not name: name = "NN-%s" % str(user_id)
                users.append(User(uid, name, privilege, password, str(group_id), str(user_id), card))
                userdata = userdata[28:]
        else:
            while len(userdata) >= 72:
                uid, privilege, password, name, card, group_id, user_id = unpack(
                    '<HB8s24sIx7sx24s', userdata.ljust(72, b'\x00')[:72])
                password = (password.split(b'\x00')[0]).decode(self.encoding, errors='ignore')
                name = (name.split(b'\x00')[0]).decode(self.encoding, errors='ignore').strip()
                group_id = (group_id.split(b'\x00')[0]).decode(self.encoding, errors='ignore').strip()
                user_id = (user_id.split(b'\x00')[0]).decode(self.encoding, errors='ignore')
                if uid > max_uid: max_uid = uid
                if not name: name = "NN-%s" % user_id
                users.append(User(uid, name, privilege, password, group_id, user_id, card))
                userdata = userdata[72:]
        max_uid += 1
        self.next_uid = max_uid
        self.next_user_id = str(max_uid)
        while True:
            if any(u for u in users if u.user_id == self.next_user_id):
                max_uid += 1
                self.next_user_id = str(max_uid)
            else:
                break
        return users

    def get_attendance(self):
        self.read_sizes()
        if self.records == 0:
            return []
        users = self.get_users()
        attendances = []
        attendance_data, size = self.read_with_buffer(const.CMD_ATTLOG_RRQ)
        if size < 4:
            return []
        total_size = unpack("I", attendance_data[:4])[0]
        record_size = total_size / self.records if self.records else 0
        attendance_data = attendance_data[4:]
        if record_size == 8:
            while len(attendance_data) >= 8:
                uid, status, timestamp, punch = unpack('HB4sB', attendance_data.ljust(8, b'\x00')[:8])
                attendance_data = attendance_data[8:]
                tuser = list(filter(lambda x: x.uid == uid, users))
                user_id = tuser[0].user_id if tuser else str(uid)
                timestamp = self.__decode_time(timestamp)
                attendances.append(Attendance(user_id, timestamp, status, punch, uid))
        elif record_size == 16:
            while len(attendance_data) >= 16:
                user_id, timestamp, status, punch, reserved, workcode = unpack(
                    '<I4sBB2sI', attendance_data.ljust(16, b'\x00')[:16])
                user_id = str(user_id)
                attendance_data = attendance_data[16:]
                tuser = list(filter(lambda x: x.user_id == user_id, users))
                uid = tuser[0].uid if tuser else str(user_id)
                timestamp = self.__decode_time(timestamp)
                attendances.append(Attendance(user_id, timestamp, status, punch, uid))
        else:
            while len(attendance_data) >= 40:
                uid, user_id, status, timestamp, punch, space = unpack(
                    '<H24sB4sB8s', attendance_data.ljust(40, b'\x00')[:40])
                user_id = (user_id.split(b'\x00')[0]).decode(errors='ignore')
                timestamp = self.__decode_time(timestamp)
                attendances.append(Attendance(user_id, timestamp, status, punch, uid))
                attendance_data = attendance_data[40:]
        return attendances

    def clear_attendance(self):
        cmd_response = self.__send_command(const.CMD_CLEAR_ATTLOG)
        if cmd_response.get('status'):
            return True
        raise ZKErrorResponse("Can't clear response")

    def live_capture(self, new_timeout=10):
        """Real-time capture of attendance events. Generator that yields Attendance objects."""
        was_enabled = self.is_enabled
        users = self.get_users()
        self.cancel_capture()
        self.verify_user()
        if not self.is_enabled:
            self.enable_device()
        self.reg_event(const.EF_ATTLOG)
        self.__sock.settimeout(new_timeout)
        self.end_live_capture = False
        while not self.end_live_capture:
            try:
                data_recv = self.__sock.recv(1032)
                self.__ack_ok()
                if self.tcp:
                    header = unpack('HHHH', data_recv[8:16])
                    data = data_recv[16:]
                else:
                    header = unpack('<4H', data_recv[:8])
                    data = data_recv[8:]
                if not header[0] == const.CMD_REG_EVENT:
                    continue
                if not len(data):
                    continue
                while len(data) >= 12:
                    if len(data) == 12:
                        user_id, status, punch, timehex = unpack('<IBB6s', data)
                        data = data[12:]
                    elif len(data) == 32:
                        user_id, status, punch, timehex = unpack('<24sBB6s', data[:32])
                        data = data[32:]
                    elif len(data) == 36:
                        user_id, status, punch, timehex, _other = unpack('<24sBB6s4s', data[:36])
                        data = data[36:]
                    elif len(data) >= 52:
                        user_id, status, punch, timehex, _other = unpack('<24sBB6s20s', data[:52])
                        data = data[52:]
                    if isinstance(user_id, int):
                        user_id = str(user_id)
                    else:
                        user_id = (user_id.split(b'\x00')[0]).decode(errors='ignore')
                    timestamp = self.__decode_timehex(timehex)
                    tuser = list(filter(lambda x: x.user_id == user_id, users))
                    uid = tuser[0].uid if tuser else int(user_id) if user_id.isdigit() else 0
                    yield Attendance(user_id, timestamp, status, punch, uid)
            except timeout:
                yield None
            except (KeyboardInterrupt, SystemExit):
                break
        self.__sock.settimeout(self.__timeout)
        self.reg_event(0)
        if not was_enabled:
            self.disable_device()

    def __recieve_chunk(self):
        if self.__response == const.CMD_DATA:
            if self.tcp:
                if len(self.__data) < (self.__tcp_length - 8):
                    need = (self.__tcp_length - 8) - len(self.__data)
                    more_data = self.__recieve_raw_data(need)
                    return b''.join([self.__data, more_data])
                else:
                    return self.__data
            else:
                return self.__data
        elif self.__response == const.CMD_PREPARE_DATA:
            data = []
            size = self.__get_data_size()
            if self.tcp:
                if len(self.__data) >= (8 + size):
                    data_recv = self.__data[8:]
                else:
                    data_recv = self.__data[8:] + self.__sock.recv(size + 32)
                resp, broken_header = self.__recieve_tcp_data(data_recv, size)
                data.append(resp)
                if len(broken_header) < 16:
                    data_recv = broken_header + self.__sock.recv(16)
                else:
                    data_recv = broken_header
                if not self.__test_tcp_top(data_recv):
                    return None
                response = unpack('HHHH', data_recv[8:16])[0]
                if response == const.CMD_ACK_OK:
                    return b''.join(data)
                return None
            while True:
                data_recv = self.__sock.recv(1024 + 8)
                response = unpack('<4H', data_recv[:8])[0]
                if response == const.CMD_DATA:
                    data.append(data_recv[8:])
                    size -= 1024
                elif response == const.CMD_ACK_OK:
                    break
                else:
                    break
            return b''.join(data)
        else:
            return None

    def __recieve_tcp_data(self, data_recv, size):
        data = []
        tcp_length = self.__test_tcp_top(data_recv)
        if tcp_length <= 0:
            return None, b""
        if (tcp_length - 8) < size:
            resp, bh = self.__recieve_tcp_data(data_recv, tcp_length - 8)
            data.append(resp)
            size -= len(resp)
            data_recv = bh + self.__sock.recv(size + 16)
            resp, bh = self.__recieve_tcp_data(data_recv, size)
            data.append(resp)
            return b''.join(data), bh
        recieved = len(data_recv)
        response = unpack('HHHH', data_recv[8:16])[0]
        if recieved >= (size + 32):
            if response == const.CMD_DATA:
                resp = data_recv[16: size + 16]
                return resp, data_recv[size + 16:]
            else:
                return None, b""
        else:
            data.append(data_recv[16: size + 16])
            size -= recieved - 16
            broken_header = b""
            if size > 0:
                data_recv = self.__recieve_raw_data(size)
                data.append(data_recv)
            return b''.join(data), broken_header

    def __recieve_raw_data(self, size):
        data = []
        while size > 0:
            data_recv = self.__sock.recv(size)
            data.append(data_recv)
            size -= len(data_recv)
        return b''.join(data)

    def __read_chunk(self, start, size):
        for _retries in range(3):
            command_string = pack('<ii', start, size)
            response_size = size + 32 if self.tcp else 1024 + 8
            cmd_response = self.__send_command(1504, command_string, response_size)
            data = self.__recieve_chunk()
            if data is not None:
                return data
        raise ZKErrorResponse("can't read chunk %i:[%i]" % (start, size))

    def read_with_buffer(self, command, fct=0, ext=0):
        MAX_CHUNK = 0xFFc0 if self.tcp else 16 * 1024
        command_string = pack('<bhii', 1, command, fct, ext)
        data = []
        start = 0
        cmd_response = self.__send_command(1503, command_string, 1024)
        if not cmd_response.get('status'):
            raise ZKErrorResponse("RWB Not supported")
        if cmd_response['code'] == const.CMD_DATA:
            if self.tcp:
                if len(self.__data) < (self.__tcp_length - 8):
                    need = (self.__tcp_length - 8) - len(self.__data)
                    more_data = self.__recieve_raw_data(need)
                    return b''.join([self.__data, more_data]), len(self.__data) + len(more_data)
                else:
                    return self.__data, len(self.__data)
            else:
                return self.__data, len(self.__data)
        size = unpack('I', self.__data[1:5])[0]
        remain = size % MAX_CHUNK
        packets = (size - remain) // MAX_CHUNK
        for _wlk in range(packets):
            data.append(self.__read_chunk(start, MAX_CHUNK))
            start += MAX_CHUNK
        if remain:
            data.append(self.__read_chunk(start, remain))
            start += remain
        self.free_data()
        return b''.join(data), start

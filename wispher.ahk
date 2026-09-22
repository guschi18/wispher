; Wispher – AutoHotkey Hotkey Handler (AHK v1)
; Sends START on F12 down, STOP on F12 up via TCP to Python daemon.

#NoEnv
#SingleInstance Force
SetWorkingDir %A_ScriptDir%

WISPHER_HOST := "127.0.0.1"
WISPHER_PORT := 9901

; ── F12 key down → START recording ──────────────────────────────────────────
F12::
  Wispher_Send("START")
return

; ── F12 key up → STOP recording ─────────────────────────────────────────────
F12 Up::
  Wispher_Send("STOP")
return

; ── Helper: open TCP connection, send message, close ─────────────────────────
Wispher_Send(msg) {
  global WISPHER_HOST, WISPHER_PORT
  sock := ""
  try {
    sock := new _Socket()
    if (!sock.Connect(WISPHER_HOST, WISPHER_PORT)) {
      ; Python daemon not running – fail silently
      return
    }
    sock.SendText(msg . "`n")
    sock.Close()
  } catch e {
    ; Silently ignore connection errors (daemon not started)
  }
}

; ── Minimal TCP socket class for AHK v1 ─────────────────────────────────────
class _Socket {
  __New() {
    this.socket := -1
  }

  Connect(host, port) {
    ; Initialize WinSock
    VarSetCapacity(wsaData, 400)
    if (DllCall("ws2_32\WSAStartup", "UShort", 0x0202, "Ptr", &wsaData) != 0)
      return false

    ; Create socket
    this.socket := DllCall("ws2_32\socket", "Int", 2, "Int", 1, "Int", 6, "Ptr")
    if (this.socket = -1)
      return false

    ; Resolve hostname → IP (simple: assume IP string)
    ip := host
    addr := inet_addr(ip)

    ; Build sockaddr_in
    VarSetCapacity(sockaddr, 16, 0)
    NumPut(2,    sockaddr, 0, "UShort")         ; AF_INET
    NumPut(this._htons(port), sockaddr, 2, "UShort")
    NumPut(addr, sockaddr, 4, "UInt")

    result := DllCall("ws2_32\connect", "Ptr", this.socket, "Ptr", &sockaddr, "Int", 16)
    return (result = 0)
  }

  SendText(text) {
    VarSetCapacity(buf, StrPut(text, "UTF-8"), 0)
    len := StrPut(text, &buf, "UTF-8") - 1  ; exclude null terminator
    DllCall("ws2_32\send", "Ptr", this.socket, "Ptr", &buf, "Int", len, "Int", 0)
  }

  Close() {
    if (this.socket != -1) {
      DllCall("ws2_32\closesocket", "Ptr", this.socket)
      DllCall("ws2_32\WSACleanup")
      this.socket := -1
    }
  }

  _htons(port) {
    return ((port & 0xFF) << 8) | ((port >> 8) & 0xFF)
  }
}

; Helper: inet_addr via DllCall
inet_addr(ip) {
  return DllCall("ws2_32\inet_addr", "AStr", ip, "UInt")
}

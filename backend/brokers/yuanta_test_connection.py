"""元大 API UAT 連線測試腳本（執行完自動離線）"""
import os
import sys
import time
import threading
from pathlib import Path
from pythonnet import load

load("coreclr")

import clr  # noqa: E402

DLL_DIR = r"C:\Users\ERIC\Downloads\YuantaSparkAPI_win-x64_Python\YuantaSparkAPI_win-x64_Python"
sys.path.append(DLL_DIR)
os.add_dll_directory(DLL_DIR)

clr.AddReference("System.Collections")
clr.AddReference("YuantaSparkAPI")

from YuantaOneAPI import (  # noqa: E402
    YuantaSparkAPITrader,
    enumEnvironmentMode,
    enumLogType,
    OnResponseEventHandler,
)

login_event = threading.Event()
login_result: dict = {}


def on_response(int_mark, dw_index, str_index, obj_handle, obj_value):
    if int_mark == 0:
        print(f"[系統] {obj_value}")
    elif int_mark == 1:
        print(f"[查詢回應] strIndex={str_index}")
        if str_index == "Login":
            try:
                status = obj_value.LoginStatus
                login_result["code"] = str(status.MsgCode)
                login_result["msg"] = str(status.MsgContent)
                login_result["count"] = int(status.Count)
                if status.Count > 0:
                    accs = obj_value.LoginList
                    login_result["accounts"] = [
                        str(accs[i].Account) for i in range(status.Count)
                    ]
            except Exception as exc:
                login_result["error"] = str(exc)
            login_event.set()
    elif int_mark == 2:
        print(f"[訂閱推送] strIndex={str_index}")


api = YuantaSparkAPITrader()
api.OnResponse += OnResponseEventHandler(on_response)
api.SetLogType(enumLogType.COMMON)

print("=== Step 1: Open UAT ===")
api.Open(enumEnvironmentMode.UAT)
time.sleep(1)

print("=== Step 2: Login ===")
api.Login("S98875005091", "1234")

print("等待登入回應（最多 10 秒）...")
if login_event.wait(timeout=10):
    code = login_result.get("code", "?")
    msg = login_result.get("msg", "?")
    count = login_result.get("count", 0)
    accs = login_result.get("accounts", [])
    err = login_result.get("error")
    print(f"登入結果: code={code}  msg={msg}  帳號數={count}")
    if accs:
        print(f"帳號清單: {accs}")
    if err:
        print(f"解析錯誤: {err}")
else:
    print("逾時，未收到 Login 回應（請確認網路/IP 白名單）")

print("=== Step 3: LogOut & Close ===")
api.LogOut()
time.sleep(0.5)
api.Close()
api.Dispose()
print("=== 完成 ===")

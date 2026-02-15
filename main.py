import sys
import os
import time
import traceback
import ctypes
import pyautogui
import win32gui
import win32con
import win32com.client
import pvporcupine
from pvrecorder import PvRecorder
from dotenv import load_dotenv

# --- 核心改动：资源路径处理函数 ---
def resource_path(relative_path):
    """
    获取资源绝对路径。
    开发时：返回当前文件所在的目录/relative_path
    打包后：返回 PyInstaller 临时目录(_MEIPASS)/relative_path
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# --- 配置区 ---

# 1. 路径设置 (全部使用 resource_path 包裹)
# 注意：打包时会将 data 文件夹里的东西平铺或保持结构，这里假设保持结构
IMG_CALL = resource_path('call.png')      
IMG_HANGUP = resource_path('hangup.png')  

MODEL_PATH_CALL = resource_path(os.path.join('data', '你好豆包_zh_windows_v4_0_0.ppn'))
MODEL_PATH_HANGUP = resource_path(os.path.join('data', '再见吧_zh_windows_v4_0_0.ppn'))
MODEL_PATH_PARAMS = resource_path(os.path.join('data', 'porcupine_params_zh.pv'))

# 2. 加载环境变量
# 如果你希望用户在 exe 旁边放 .env 文件，用 os.getcwd()
# 如果你希望 .env 打包进 exe 内部（不安全，不推荐），用 resource_path
# 这里采用：优先读取 exe 同级目录下的 .env，方便用户修改 Key
env_path_external = os.path.join(os.getcwd(), '.env')
env_path_internal = resource_path('.env')

if os.path.exists(env_path_external):
    load_dotenv(env_path_external)
    print(f"加载外部配置: {env_path_external}")
else:
    load_dotenv(env_path_internal)
    print("加载内部默认配置")

PICOVOICE_API_KEY = os.getenv("PICOVOICE_API_KEY")

if not PICOVOICE_API_KEY:
    # 增加 input 防止报错后窗口秒关，用户看不到报错
    print("错误：未找到 PICOVOICE_API_KEY，请在 .env 文件中配置。")
    input("按回车键退出...")
    sys.exit(1)

# 3. 窗口标题
WINDOW_TITLE = "豆包"

# --- 核心功能区 (保持不变，仅修正打印逻辑) ---

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class WindowManager:
    def __init__(self, title_keyword):
        self.title_keyword = title_keyword
        self.hwnd = None

    def find_window(self):
        self.hwnd = None
        win32gui.EnumWindows(self._enum_cb, None)
        return self.hwnd

    def _enum_cb(self, hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if self.title_keyword in title:
                self.hwnd = hwnd

    def activate_and_get_region(self):
        if not self.find_window():
            print(f"   [错误] 未找到标题包含 '{self.title_keyword}' 的窗口")
            return None

        try:
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%') 
            win32gui.SetForegroundWindow(self.hwnd)
            
            time.sleep(0.2)
            
            rect = win32gui.GetWindowRect(self.hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y
            return (x, y, w, h)
        except Exception as e:
            print(f"   [窗口激活失败] {e}")
            return None

doubao_win = WindowManager(WINDOW_TITLE)

def smart_click(img_path, action_name):
    print(f"\n--- 执行指令：{action_name} ---")
    region = doubao_win.activate_and_get_region()
    
    if not region:
        return

    try:
        if not os.path.exists(img_path):
            print(f"   [错误] 图片资源丢失: {img_path}")
            return

        location = pyautogui.locateOnScreen(
            img_path, 
            region=region, 
            confidence=0.8,
            grayscale=True 
        )
        
        if location:
            x, y = pyautogui.center(location)
            print(f"   -> 锁定坐标: ({x}, {y})")
            
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.mouseDown()
            time.sleep(0.1)
            pyautogui.mouseUp()
            
            time.sleep(0.1)
            pyautogui.moveTo(10, 10, duration=0.1)
            print(f"   -> {action_name} 成功")
        else:
            print(f"   [失败] 窗口内未找到图标")
            
    except Exception as e:
        print(f"   [异常] {e}")

# --- 主程序 ---

def main():
    try:
        if not os.path.exists(MODEL_PATH_PARAMS):
            raise FileNotFoundError(f"模型文件丢失: {MODEL_PATH_PARAMS}")

        porcupine = pvporcupine.create(
            access_key=PICOVOICE_API_KEY, 
            keyword_paths=[MODEL_PATH_CALL, MODEL_PATH_HANGUP],
            model_path=MODEL_PATH_PARAMS
        )
        
        print(f"Picovoice 初始化成功！") 

    except Exception as e:
        print(f"初始化失败: {e}")
        input("按回车键退出...") # 防止闪退
        return

    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    
    print(f"=== 语音助手 (v1.0) 启动成功 ===")
    print(f"配置文件路径: {env_path_external}")
    print(f"1. 说 '你好豆包' -> 拨打")
    print(f"2. 说 '再见吧'   -> 挂断")
    print(f"(请勿关闭此窗口，Ctrl+C 可退出)")
    
    try:
        recorder.start()
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index == 0:
                print(f"\n[听到: 你好豆包]")
                smart_click(IMG_CALL, "拨打")
                time.sleep(1.0)
                
            elif keyword_index == 1:
                print(f"\n[听到: 再见吧]")
                smart_click(IMG_HANGUP, "挂断")
                time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n停止")
    except Exception as e:
        print(f"\n运行时错误: {e}")
        traceback.print_exc()
        input("按回车键退出...")
    finally:
        if 'recorder' in locals(): recorder.stop(); recorder.delete()
        if 'porcupine' in locals(): porcupine.delete()

if __name__ == "__main__":
    main()
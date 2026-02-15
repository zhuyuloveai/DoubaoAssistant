import pvporcupine
from pvrecorder import PvRecorder
import pyautogui
import win32gui
import win32con
import win32com.client
import time
import os
import traceback
import ctypes
from dotenv import load_dotenv

# --- 配置区 ---

# 1. 路径设置
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
data_dir = os.path.join(current_dir, 'data')

# 图片路径 (建议重新截图，只截取按钮本身，不含背景)
IMG_CALL = os.path.join(current_dir, 'call.png')      
IMG_HANGUP = os.path.join(current_dir, 'hangup.png')  

# 模型路径
MODEL_PATH_CALL = os.path.join(data_dir, '你好豆包_zh_windows_v4_0_0.ppn')
MODEL_PATH_HANGUP = os.path.join(data_dir, '再见吧_zh_windows_v4_0_0.ppn')
MODEL_PATH_PARAMS = os.path.join(data_dir, 'porcupine_params_zh.pv')

# 2. 加载环境变量
load_dotenv(env_path)
PICOVOICE_API_KEY = os.getenv("PICOVOICE_API_KEY")

if not PICOVOICE_API_KEY:
    raise ValueError("错误：未找到 PICOVOICE_API_KEY，请检查 .env 文件。")

# 3. 窗口标题 (必须准确，可以用 Spy++ 或简单的 print 脚本确认)
WINDOW_TITLE = "豆包"

# --- 核心功能区 ---

# 强制开启 DPI 感知，防止坐标偏移
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class WindowManager:
    """封装 Windows API 用于窗口控制"""
    
    def __init__(self, title_keyword):
        self.title_keyword = title_keyword
        self.hwnd = None

    def find_window(self):
        """查找包含指定标题的窗口句柄"""
        self.hwnd = None
        win32gui.EnumWindows(self._enum_cb, None)
        return self.hwnd

    def _enum_cb(self, hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if self.title_keyword in title:
                self.hwnd = hwnd

    def activate_and_get_region(self):
        """激活窗口并返回其坐标区域 (left, top, width, height)"""
        if not self.find_window():
            print(f"   [错误] 未找到标题包含 '{self.title_keyword}' 的窗口")
            return None

        try:
            # 1. 如果最小化了，还原它
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            
            # 2. 强力置顶 (使用 Shell Hack 防止被 Windows 拦截)
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys('%') # 发送 Alt 键欺骗系统
            win32gui.SetForegroundWindow(self.hwnd)
            
            # 3. 等待窗口动画结束
            time.sleep(0.2)
            
            # 4. 获取窗口坐标
            rect = win32gui.GetWindowRect(self.hwnd)
            x, y, x2, y2 = rect
            w = x2 - x
            h = y2 - y
            
            return (x, y, w, h)
            
        except Exception as e:
            print(f"   [窗口激活失败] {e}")
            return None

# 初始化窗口管理器
doubao_win = WindowManager(WINDOW_TITLE)

def smart_click(img_path, action_name):
    print(f"\n--- 执行指令：{action_name} ---")
    
    # 1. 尝试激活窗口并获取区域
    region = doubao_win.activate_and_get_region()
    
    if not region:
        print("   无法定位窗口，放弃操作。")
        return

    print(f"   窗口区域锁定: {region}")

    try:
        if not os.path.exists(img_path):
            print(f"   [错误] 图片不存在: {img_path}")
            return

        # 2. 在指定区域内找图 (Region 限制搜索范围)
        # grayscale=True: 忽略按钮高亮色差
        location = pyautogui.locateOnScreen(
            img_path, 
            region=region, 
            confidence=0.8,
            grayscale=True 
        )
        
        if location:
            # 3. 获取中心坐标 (pyautogui 返回的是屏幕绝对坐标)
            x, y = pyautogui.center(location)
            print(f"   -> 锁定按钮坐标: ({x}, {y})")
            
            # 4. 执行点击动作
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.mouseDown()
            time.sleep(0.1) # 模拟按压
            pyautogui.mouseUp()
            print(f"   -> {action_name} 点击完成")
            
            # 5. 【关键】鼠标归位
            # 移到屏幕左上角 (10, 10)，防止遮挡或残留 Hover 状态
            time.sleep(0.1)
            pyautogui.moveTo(10, 10, duration=0.1)
            
        else:
            print(f"   [查找失败] 在窗口内未找到图标。请检查截图是否准确。")
            
    except Exception as e:
        print(f"   [异常] {e}")

# --- 主程序 ---

def main():
    try:
        # 检查模型文件
        if not os.path.exists(MODEL_PATH_PARAMS):
            raise FileNotFoundError("找不到中文模型文件 porcupine_params_zh.pv")

        porcupine = pvporcupine.create(
            access_key=PICOVOICE_API_KEY, 
            keyword_paths=[MODEL_PATH_CALL, MODEL_PATH_HANGUP],
            model_path=MODEL_PATH_PARAMS
        )
        
        print("Picovoice 初始化成功！") 

    except Exception as e:
        print(f"初始化失败: {e}")
        return

    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    
    print(f"=== 语音助手 (主窗口模式) 运行中 ===")
    print(f"1. 说 '你好豆包' -> 激活窗口并拨打")
    print(f"2. 说 '再见吧'   -> 激活窗口并挂断")
    
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
    finally:
        if 'recorder' in locals(): recorder.stop(); recorder.delete()
        if 'porcupine' in locals(): porcupine.delete()

if __name__ == "__main__":
    main()
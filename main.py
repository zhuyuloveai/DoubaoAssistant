import pvporcupine
from pvrecorder import PvRecorder
import pyautogui
import pygetwindow as gw
import time

# --- 配置区 ---
PICOVOICE_API_KEY = "你的Access_Key" # 替换为你申请的 Key
WAKE_WORD = "computer"  # 默认唤醒词，也可以选 'jarvis', 'porcupine' 等
DB_HOTKEY = ('alt', 'space') # 豆包的快捷键

def get_doubao_window():
    """获取豆包窗口对象"""
    try:
        wins = gw.getWindowsWithTitle('豆包')
        return wins[0] if wins else None
    except:
        return None

def trigger_dialog():
    """唤醒并进入对话逻辑"""
    print(">>> 检测到唤醒词，正在启动对话...")
    win = get_doubao_window()
    
    # 1. 确保豆包窗口呼出
    # 如果窗口不存在或者不可见，按快捷键
    pyautogui.hotkey(*DB_HOTKEY)
    time.sleep(0.5) # 等待窗口动画
    
    # 2. 图像识别寻找“电话”图标并点击
    try:
        # confidence是匹配精度，0.8比较稳。grayscale=True可以加快速度
        call_location = pyautogui.locateOnScreen('call.png', confidence=0.8, grayscale=True)
        if call_location:
            pyautogui.click(pyautogui.center(call_location))
            print("成功进入实时对话模式")
        else:
            print("未找到通话按钮，请确认豆包界面是否正确")
    except Exception as e:
        print(f"识别出错: {e}")

def close_dialog():
    """挂断并隐藏对话"""
    print(">>> 正在结束对话...")
    try:
        hangup_location = pyautogui.locateOnScreen('hangup.png', confidence=0.8, grayscale=True)
        if hangup_location:
            pyautogui.click(pyautogui.center(hangup_location))
            time.sleep(0.3)
        
        # 隐藏窗口
        pyautogui.hotkey(*DB_HOTKEY)
    except Exception as e:
        print(f"关闭失败: {e}")

# --- 主程序循环 ---
def main():
    porcupine = pvporcupine.create(access_key=PICOVOICE_API_KEY, keywords=[WAKE_WORD])
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    
    print(f"语音助手已就绪，喊 '{WAKE_WORD}' 唤醒我...")
    
    try:
        recorder.start()
        while True:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            
            if result >= 0:
                trigger_dialog()
                
                # 这里进入一个简单的次级监听，或者设定几分钟后自动关闭
                # 为了简化，本脚本只负责唤醒。
                # 如果需要语音关闭，可以再写一个简单的关键词识别逻辑。

    except KeyboardInterrupt:
        print("停止运行")
    finally:
        recorder.stop()
        porcupine.delete()

if __name__ == "__main__":
    main()
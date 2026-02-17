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

def get_runtime_dir():
    """运行时目录：开发为脚本目录；打包为 exe 所在目录。"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_resources_root():
    """
    获取资源根目录（与 exe 解耦）。
    开发时：使用与 main.py 同级的 resources/
    打包后：使用与 exe 同级的 resources/
    注意：resources 不再打包进 exe 内部；如果缺失则直接报错提示。
    """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    external = os.path.join(exe_dir, 'resources')
    if os.path.isdir(external):
        return external
    raise FileNotFoundError(
        "未找到资源目录 resources/。\n"
        f"请在以下路径旁放置 resources 目录：{exe_dir}\n"
        "示例：resources/call/*.png、resources/hangup/*.png"
    )

def _debug_enabled():
    v = os.getenv("DOUBAO_DEBUG_VISION", "").strip().lower()
    return v in ("1", "true", "yes", "y", "on")

def _ensure_debug_dir():
    d = os.path.join(get_runtime_dir(), "debug")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        return None
    return d

def _safe_image_size(img_path: str):
    try:
        from PIL import Image
        with Image.open(img_path) as im:
            return im.size
    except Exception:
        return None


# 支持的图片扩展名
IMG_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp')


def _collect_images_from_dir(directory, skip_subdir_name=None):
    """从目录递归收集图片路径，可跳过指定子目录名（避免重复）。"""
    out = []
    try:
        names = sorted(os.listdir(directory))
        for name in names:
            full = os.path.join(directory, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in IMG_EXTENSIONS:
                out.append(full)
        for name in names:
            if name == skip_subdir_name:
                continue
            full = os.path.join(directory, name)
            if os.path.isdir(full):
                out.extend(_collect_images_from_dir(full, None))
    except OSError:
        pass
    return out


def get_scene_image_paths(scene_name):
    """
    按场景名获取该场景下所有图片路径（含子目录），用于多分辨率遍历匹配。
    scene_name: 场景目录名，如 'call'、'hangup'
    返回: 有序列表，优先当前分辨率子目录（如 1920x1080），再根目录及其余子目录
    """
    root = get_resources_root()
    scene_dir = os.path.join(root, scene_name)
    if not os.path.isdir(scene_dir):
        return []

    res_subdir = None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        res_subdir = f"{w}x{h}"
    except Exception:
        pass

    paths = []
    res_subdir_path = os.path.join(scene_dir, res_subdir) if res_subdir else None
    if res_subdir_path and os.path.isdir(res_subdir_path):
        paths.extend(_collect_images_from_dir(res_subdir_path))
    paths.extend(_collect_images_from_dir(scene_dir, res_subdir))
    return paths


# --- 配置区 ---

# 1. 路径设置 (全部使用 resource_path 包裹)
# 图片资源已迁移到 resources/<场景名>/，见 get_resources_root、get_scene_image_paths  

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

def smart_click(image_paths, action_name):
    """
    在窗口区域内依次尝试 image_paths 中的图片，直到某张匹配则点击。
    image_paths: 图片路径列表（通常来自 get_scene_image_paths(scene_name)）
    """
    print(f"\n--- 执行指令：{action_name} ---")
    region = doubao_win.activate_and_get_region()
    
    if not region:
        return

    if not image_paths:
        print(f"   [错误] 场景无图片资源，请检查 resources 目录下对应场景文件夹")
        return

    print(f"   -> 搜索区域(region): {region}")
    print(f"   -> 待尝试图片数: {len(image_paths)}")
    if _debug_enabled():
        try:
            print(f"   [DEBUG] runtime_dir: {get_runtime_dir()}")
            print(f"   [DEBUG] resources_root: {get_resources_root()}")
            print(f"   [DEBUG] screen_size: {pyautogui.size()}")
        except Exception as e_dbg:
            print(f"   [DEBUG] basic info failed: {type(e_dbg).__name__} | {e_dbg!r}")

    try:
        for idx, img_path in enumerate(image_paths, start=1):
            if not os.path.exists(img_path):
                print(f"   [跳过] 文件不存在: {img_path}")
                continue

            try:
                location = pyautogui.locateOnScreen(
                    img_path,
                    region=region,
                    confidence=0.8,
                    grayscale=True
                )
            except pyautogui.ImageNotFoundException:
                # PyAutoGUI 新版本可能会在“未命中”时抛异常；这不是运行错误，视为未找到
                location = None
            except Exception as e_img:
                print(
                    f"   [异常] locateOnScreen 运行错误 ({idx}/{len(image_paths)}): "
                    f"{os.path.basename(img_path)} | {type(e_img).__name__} | {e_img!r}"
                )
                traceback.print_exc()
                continue

            if location:
                x, y = pyautogui.center(location)
                print(f"   -> 使用: {os.path.basename(img_path)} 锁定坐标: ({x}, {y})")
                pyautogui.moveTo(x, y, duration=0.2)
                pyautogui.mouseDown()
                time.sleep(0.1)
                pyautogui.mouseUp()
                time.sleep(0.1)
                pyautogui.moveTo(10, 10, duration=0.1)
                print(f"   -> {action_name} 成功")
                return
            else:
                if _debug_enabled():
                    sz = _safe_image_size(img_path)
                    if sz:
                        print(f"   [DEBUG] miss ({idx}/{len(image_paths)}): {os.path.basename(img_path)} size={sz}")
                    else:
                        print(f"   [DEBUG] miss ({idx}/{len(image_paths)}): {os.path.basename(img_path)}")

        print(f"   [失败] 窗口内未找到图标（已尝试 {len(image_paths)} 张图）")
        if _debug_enabled():
            debug_dir = _ensure_debug_dir()
            if debug_dir:
                ts = time.strftime("%Y%m%d_%H%M%S")
                try:
                    snap_path = os.path.join(debug_dir, f"{action_name}_region_{ts}.png")
                    pyautogui.screenshot(snap_path, region=region)
                    print(f"   [DEBUG] saved region screenshot: {snap_path}")
                except Exception as e_shot:
                    print(f"   [DEBUG] save screenshot failed: {type(e_shot).__name__} | {e_shot!r}")
    except Exception as e:
        print(f"   [异常] smart_click 崩溃: {type(e).__name__} | {e!r}")
        traceback.print_exc()

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
    print(f"(提示：为避免启动瞬间误触发，前 2 秒会忽略唤醒词)")
    
    try:
        recorder.start()
        start_ts = time.time()
        last_trigger_ts = 0.0
        arm_delay_seconds = float(os.getenv("ARM_DELAY_SECONDS", "2.0") or "2.0")
        cooldown_seconds = float(os.getenv("COMMAND_COOLDOWN_SECONDS", "1.5") or "1.5")
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            
            if keyword_index == 0:
                now = time.time()
                if now - start_ts < arm_delay_seconds:
                    continue
                if now - last_trigger_ts < cooldown_seconds:
                    continue
                last_trigger_ts = now
                print(f"\n[听到: 你好豆包]")
                smart_click(get_scene_image_paths('call'), "拨打")
                time.sleep(1.0)
                
            elif keyword_index == 1:
                now = time.time()
                if now - start_ts < arm_delay_seconds:
                    continue
                if now - last_trigger_ts < cooldown_seconds:
                    continue
                last_trigger_ts = now
                print(f"\n[听到: 再见吧]")
                hangup_delay_seconds = float(os.getenv("HANGUP_DELAY_SECONDS", "5.0") or "5.0")
                if hangup_delay_seconds > 0:
                    print(f"   -> 将在 {hangup_delay_seconds:.1f} 秒后挂断（等待豆包说完告别语）")
                    time.sleep(hangup_delay_seconds)
                smart_click(get_scene_image_paths('hangup'), "挂断")
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
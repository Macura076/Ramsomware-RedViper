import os
import threading
import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import time
import winsound

# somente Windows
if os.name != "nt":
    raise SystemExit("Este script só funciona no Windows.")

# ===== WinAPI / constantes =====
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

VK_TAB = 0x09
VK_F4 = 0x73
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_D = 0x44
VK_M = 0x4D
VK_R = 0x52
VK_L = 0x4C
VK_E = 0x45
VK_ESC = 0x1B
VK_CONTROL = 0x11
VK_SHIFT = 0x10

LLKHF_ALTDOWN = 0x20
HC_ACTION = 0

LRESULT = wintypes.LPARAM
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = (wintypes.INT, HOOKPROC, wintypes.HMODULE, wintypes.DWORD)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]

# ===== Hook global que suprime Win/Alt-Tab/Alt-F4/Win+letras =====
class GlobalKeyBlocker:
    def __init__(self):
        self.hook = None
        self.proc = None
        try:
            self._install()
            self.ok = True
        except Exception as e:
            self.ok = False
            self._error = str(e)

    def _install(self):
        if self.hook:
            return

        @HOOKPROC
        def low_level_proc(nCode, wParam, lParam):
            try:
                if nCode == HC_ACTION and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                    vk = kb.vkCode
                    alt_down = (kb.flags & LLKHF_ALTDOWN) != 0

                    if vk in (VK_LWIN, VK_RWIN):  # Bloquear tecla Windows
                        return 1
                    if alt_down and vk in (VK_TAB, VK_F4):  # Alt+Tab / Alt+F4
                        return 1
                    if (user32.GetAsyncKeyState(VK_LWIN) & 0x8000) or (user32.GetAsyncKeyState(VK_RWIN) & 0x8000):
                        if vk in (VK_D, VK_M, VK_R, VK_L, VK_E):  # Win + letras
                            return 1
                    ctrl_pressed = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
                    shift_pressed = user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
                    if ctrl_pressed and shift_pressed and vk == VK_ESC:  # Ctrl+Shift+Esc
                        return 1
            except Exception:
                pass
            return user32.CallNextHookEx(self.hook, nCode, wParam, lParam)

        self.proc = low_level_proc
        hmod = kernel32.GetModuleHandleW(None)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.proc, hmod, 0)
        if not self.hook:
            raise RuntimeError("SetWindowsHookExW falhou (hook não instalado).")

        def pump():
            msg = wintypes.MSG()
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
                if ret == 0 or ret == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        t = threading.Thread(target=pump, daemon=True)
        t.start()

    def uninstall(self):
        try:
            if self.hook:
                user32.UnhookWindowsHookEx(self.hook)
        except Exception:
            pass
        finally:
            self.hook = None
            self.proc = None

# ===== GUI fullscreen =====
class SecureFullScreen:
    def __init__(self, unlock_key="RedViper"):
        possible_paths = [r"D:\imagens\foto.png", r"C:\imagens\foto.png"]
        self.img_path = next((p for p in possible_paths if os.path.exists(p)), None)

        self.unlock_key = unlock_key
        self.root = tk.Tk()
        self.root.title("Tela Segura")
        self.root.configure(bg="black")
        self.root.attributes("-fullscreen", True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

        self.blocker = GlobalKeyBlocker()

        self.container = tk.Frame(self.root, bg="black")
        self.container.pack(expand=True, fill="both")

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # Título "RedViper" no topo da tela
        self.title_label = tk.Label(
            self.container, 
            text="REDVIPER",
            fg="red", 
            bg="black", 
            font=("Courier", 36, "bold"),
            pady=20
        )
        self.title_label.pack(fill="x")

        if self.img_path:
            self._load_image()
        else:
            tk.Label(self.container, text="Imagem não encontrada em C: ou D:", 
                     fg="white", bg="black", font=("Arial", 18)).pack(pady=20)

        self._create_timer_and_input()

    def _load_image(self):
        try:
            img = Image.open(self.img_path)
            max_w = int(self.screen_w * 0.6)
            max_h = int(self.screen_h * 0.45)
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(img)
            self.img_label = tk.Label(self.container, image=self.photo, bg="black", bd=0)
            self.img_label.pack(pady=20)  # Posiciona a imagem abaixo do título
        except Exception:
            tk.Label(self.container, text="Erro ao carregar imagem", fg="white", bg="black", font=("Arial", 18)).pack(pady=20)

    def _create_timer_and_input(self):
        self.tempo_restante = 35 * 60
        self.timer_label = tk.Label(self.container, text="", fg="red", bg="black", font=("Courier", 36, "bold"))
        self.timer_label.pack(pady=10)

        # Frame para a área de entrada (sem borda vermelha)
        input_frame = tk.Frame(self.container, bg='black')
        input_frame.pack(pady=20)
        
        # Caixa de texto
        self.chave_entry = tk.Entry(
            input_frame,
            bg='black',
            fg='red',
            font=('Courier', 16),
            insertbackground='red',
            justify='center',
            relief='solid',
            bd=1,
            show="*",
            width=25
        )
        self.chave_entry.pack(pady=10, padx=10)
        
        # Configurar placeholder
        self.placeholder_text = "Enter key here..."
        self.chave_entry.insert(0, self.placeholder_text)
        self.chave_entry.config(fg='grey')
        self.chave_entry.bind('<FocusIn>', self.clear_placeholder)
        self.chave_entry.bind('<FocusOut>', self.set_placeholder)
        self.chave_entry.bind('<Key>', self.on_key_press)
        
        # Botão de confirmação
        confirm_btn = tk.Button(
            input_frame,
            text="Confirm",
            bg='black',
            fg='red',
            font=('Courier', 14),
            relief='solid',
            bd=1,
            command=self.verificar_chave,
            padx=20,
            pady=5
        )
        confirm_btn.pack(pady=10)
        
        # Configurar as bordas vermelhas apenas nos elementos
        self.chave_entry.config(highlightbackground='red', highlightcolor='red', highlightthickness=1)
        confirm_btn.config(highlightbackground='red', highlightcolor='red', highlightthickness=1)

        self._update_timer()
        self.chave_entry.bind("<Return>", lambda e: self.verificar_chave())
        self.chave_entry.focus_set()

        self.root.bind_all("<Key>", self._tk_fallback_block)
        
        # Variável para controlar se é a primeira vez que o usuário digita após erro
        self.placeholder_active = True

    def clear_placeholder(self, event):
        if self.placeholder_active:
            self.chave_entry.delete(0, tk.END)
            self.chave_entry.config(fg='red')
            self.placeholder_active = False

    def set_placeholder(self, event):
        if not self.chave_entry.get():
            self.chave_entry.insert(0, self.placeholder_text)
            self.chave_entry.config(fg='grey')
            self.placeholder_active = True

    def on_key_press(self, event):
        # Se o placeholder estiver ativo e o usuário pressionar qualquer tecla, limpar o campo
        if self.placeholder_active:
            self.chave_entry.delete(0, tk.END)
            self.chave_entry.config(fg='red')
            self.placeholder_active = False

    def _update_timer(self):
        minutos = self.tempo_restante // 60
        segundos = self.tempo_restante % 60
        self.timer_label.config(text=f"{minutos:02}:{segundos:02}")
        if self.tempo_restante > 0:
            self.tempo_restante -= 1
            self.root.after(1000, self._update_timer)
        else:
            self.timer_label.config(text="Tempo esgotado!")
            self._start_alarm_and_flash()

    def _start_alarm_and_flash(self):
        threading.Thread(target=self._play_alarm, daemon=True).start()
        self._flash_once()

    def _play_alarm(self):
        try:
            for _ in range(3):
                winsound.Beep(1200, 400)
                winsound.Beep(800, 300)
        except Exception:
            pass

    def _flash_once(self):
        try:
            old_bg = self.root.cget("bg")
            def do_flash(times):
                if times <= 0:
                    self.root.configure(bg=old_bg)
                    self.timer_label.configure(bg=old_bg)
                    return
                self.root.configure(bg="red")
                self.timer_label.configure(bg="red")
                self.root.after(400, lambda: revert_then(times))
            def revert_then(times):
                self.root.configure(bg=old_bg)
                self.timer_label.configure(bg=old_bg)
                self.root.after(150, lambda: do_flash(times - 1))
            do_flash(2)
        except Exception:
            pass

    def verificar_chave(self):
        if self.chave_entry.get() == self.unlock_key:
            try:
                self.blocker.uninstall()
            except Exception:
                pass
            self.root.destroy()
        else:
            messagebox.showerror("Erro", "Chave incorreta!")
            self.chave_entry.delete(0, tk.END)
            self.set_placeholder(None)
            self.chave_entry.focus_set()
            try:
                threading.Thread(target=lambda: winsound.Beep(1000, 200), daemon=True).start()
            except Exception:
                pass

    def _tk_fallback_block(self, event):
        try:
            if event.keysym in ("Super_L", "Super_R", "Win_L", "Win_R"):
                return "break"
            state = event.state
            if state in (8, 9, 12, 13) and event.keysym.lower() in ('d', 'l', 'r', 'm'):
                return "break"
            if state in (8, 9, 12, 13) and event.keysym == "F4":
                return "break"
            if (event.state & 0x4) and (event.state & 0x1) and event.keysym == "Escape":
                return "break"
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
        try:
            self.blocker.uninstall()
        except Exception:
            pass

if __name__ == "__main__":
    app = SecureFullScreen(unlock_key="RedViper")
    app.run()

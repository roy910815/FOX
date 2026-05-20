import sys
import random
import os
import math
import time
import json
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QLabel, QWidget, QMenu, 
                             QVBoxLayout, QGroupBox, QSlider, QPushButton, QColorDialog)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QAction, QTransform, QCursor, QPainter, QColor, QImage
from pynput import mouse

# 強制螢幕縮放
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 面板介面 ---
class ControlWindow(QWidget):
    def __init__(self, pet_instance):
        super().__init__()
        self.pet = pet_instance
        self.setWindowTitle("狐狸控制中心")
        self.setFixedSize(260, 560) 
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint) 

        layout = QVBoxLayout()

        status_group = QGroupBox("📊 狐狸目前狀態")
        self.status_label = QLabel("飽食: 0 | 精力: 100 | 心情: 50 | 好感: 0")
        status_layout = QVBoxLayout()
        status_layout.addWidget(self.status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        color_group = QGroupBox("🎨 外觀顏色設定")
        color_layout = QVBoxLayout()
        self.btn_pick_color = QPushButton("選擇狐狸顏色")
        self.btn_pick_color.clicked.connect(self.pick_color)
        self.btn_reset_color = QPushButton("恢復原本顏色")
        self.btn_reset_color.clicked.connect(self.reset_color)
        color_layout.addWidget(self.btn_pick_color)
        color_layout.addWidget(self.btn_reset_color)
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)

        scale_group = QGroupBox("📏 狐狸大小調整")
        scale_layout = QVBoxLayout()
        self.scale_slider = QSlider(Qt.Orientation.Horizontal)
        self.scale_slider.setRange(1, 20) 
        self.scale_slider.setValue(int(self.pet.scale_factor * 10))
        self.scale_slider.valueChanged.connect(self.change_scale)
        scale_layout.addWidget(self.scale_slider)
        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)

        speed_group = QGroupBox("⚡ 移動速度設定")
        speed_layout = QVBoxLayout()
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 30)
        self.speed_slider.setValue(self.pet.normal_speed)
        self.speed_slider.valueChanged.connect(self.change_speed)
        speed_layout.addWidget(self.speed_slider)
        speed_group.setLayout(speed_layout)
        layout.addWidget(speed_group)

        action_group = QGroupBox("🎮 動作指令")
        action_layout = QVBoxLayout()
        self.btn_feed = QPushButton("🍖 餵食狐狸")
        self.btn_feed.clicked.connect(self.pet.feed_fox)
        self.btn_feed.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; height: 30px;")
        self.btn_pause = QPushButton("⏯️ 停止 / 開始切換")
        self.btn_pause.clicked.connect(self.pet.toggle_pause)
        self.btn_center = QPushButton("🏠 回到畫面中心")
        self.btn_center.clicked.connect(self.move_to_center)
        action_layout.addWidget(self.btn_feed) 
        action_layout.addWidget(self.btn_pause)
        action_layout.addWidget(self.btn_center)
        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        sys_group = QGroupBox("⚠️ 系統控制")
        sys_layout = QVBoxLayout()
        self.btn_close_panel = QPushButton("❌ 關閉控制面板 (保留狐狸)")
        self.btn_close_panel.clicked.connect(self.hide) 
        self.btn_close_panel.setStyleSheet("font-weight: bold;")
        self.btn_shutdown = QPushButton("🛑 讓狐狸休息")
        self.btn_shutdown.setStyleSheet("background-color: #ff4d4d; color: white; font-weight: bold;")
        self.btn_shutdown.clicked.connect(QApplication.instance().quit) 
        sys_layout.addWidget(self.btn_close_panel)
        sys_layout.addWidget(self.btn_shutdown)
        sys_group.setLayout(sys_layout)
        layout.addWidget(sys_group)

        self.setLayout(layout)

    def pick_color(self):
        initial_color = self.pet.tint_color if self.pet.tint_color else QColor(255, 120, 0)
        color = QColorDialog.getColor(initial_color, self, "選擇狐狸花色")
        if color.isValid():
            self.pet.tint_color = color
            self.pet.update_image()

    def reset_color(self):
        self.pet.tint_color = None
        self.pet.update_image()

    def update_status_text(self, h, e, m, a):
        fullness = 100 - int(h)
        self.status_label.setText(f"飽食: {fullness} | 精力: {int(e)} | 心情: {int(m)} | 好感: {int(a)}")

    def change_scale(self, value):
        self.pet.scale_factor = value / 10.0
        self.pet.update_image()

    def change_speed(self, value):
        self.pet.normal_speed = value
        if self.pet.state != "notice": self.pet.speed = value

    def move_to_center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        cx = (screen.width() - self.pet.width()) // 2
        cy = (screen.height() - self.pet.height()) // 2
        self.pet.move(cx, cy)
        self.pet.target_pos = QPoint(cx, cy)
        self.pet.state = "idle"

class GlobalSignals(QObject):
    double_clicked = pyqtSignal() 

class FoxPet(QWidget):
    def __init__(self):
        super().__init__()

        self.scale_factor = 0.4
        self.tint_color = None 
        self.is_paused = False 
        self.is_local_double_clicking = False 
        self.mouse_controller = mouse.Controller()
        self.last_activity_time = time.time()
        self.is_nuzzling = False 
        self.nuzzle_start_time = 0 
        self.is_being_petted = False
        self.pet_touch_start_time = 0
        self.is_belly_up = False
        self.is_user_intending_pet = False 
        self.pet_intent_start_time = 0 

        self.load_data() 
        self.last_stat_time = time.time()

        self.slow_anim_vector = 3 
        self.slow_tick_counter = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.SplashScreen |       
            Qt.WindowType.NoDropShadowWindowHint 
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent; border: none; outline: none;") 
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.label)
        
        self.state = "idle"  
        self.direction = 1   
        self.frame_index = 0
        self.normal_speed = 8
        self.speed = self.normal_speed 
        self.target_pos = self.pos()
        self.fall_counter = 0 
        
        self.assets = {
            "idle": [resource_path(f"assets/idle_{i}.png") for i in range(1, 5)],
            "front_idle": [resource_path(f"assets/tail_{i}.png") for i in range(1, 5)],
            "walk": [resource_path(f"assets/walk_{i}.png") for i in range(2, 9)], 
            "drag": [resource_path("assets/drag_1.png")],
            "fall": [resource_path("assets/fall_1.png")],
            "notice": [resource_path("assets/shock_1.png")],
            "sleep": [resource_path(f"assets/sleep_{i}.png") for i in range(1, 5)],
            "nuzzle": [resource_path(f"assets/nuzzle_{i}.png") for i in range(1, 6)],
            "pet": [resource_path(f"assets/touch_{i}.png") for i in range(1, 4)],
            "belly": [resource_path(f"assets/touchdown_{i}.png") for i in range(1, 4)],
            "eat": [resource_path(f"assets/eat_{i}.png") for i in range(1, 4)] 
        }
        
        self.control_panel = ControlWindow(self)
        self.update_image()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.pet_logic)
        self.timer.start(120) 

        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.save_data)
        self.save_timer.start(60000)

        QApplication.instance().aboutToQuit.connect(self.save_data)

        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self.click_timer = QTimer()
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.start_drag)

        self.signals = GlobalSignals()
        self.signals.double_clicked.connect(self.handle_global_double_click)
        self.setup_global_mouse_listener()

        self.show()

    def get_save_path(self):
        return os.path.join(os.path.abspath("."), "fox_save.json")

    def load_data(self):
        save_path = self.get_save_path()
        if os.path.exists(save_path):
            try:
                with open(save_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.hunger = data.get("hunger", 0.0)
                    self.energy = data.get("energy", 100.0)
                    self.mood = data.get("mood", 50.0)
                    self.affection = data.get("affection", 0.0)
                    color_hex = data.get("tint_color")
                    if color_hex:
                        self.tint_color = QColor(color_hex)
                    return
            except Exception:
                pass
        self.hunger, self.energy, self.mood, self.affection = 0.0, 100.0, 50.0, 0.0

    def save_data(self):
        save_path = self.get_save_path()
        data = {
            "hunger": self.hunger, "energy": self.energy, "mood": self.mood, "affection": self.affection,
            "tint_color": self.tint_color.name() if self.tint_color else None
        }
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def feed_fox(self):
        if self.state in ["drag", "fall"]: return
        self.hunger = max(0, self.hunger - 40) 
        self.mood = min(100, self.mood + 15)  
        self.affection += 2
        self.state = "eat"
        self.frame_index = 0
        self.last_activity_time = time.time()
        self.save_data() 
        QTimer.singleShot(3600, lambda: setattr(self, 'state', 'idle'))

    def update_model_stats(self):
        now = time.time()
        dt = now - self.last_stat_time
        self.last_stat_time = now
        self.hunger = min(100, self.hunger + dt * 0.1)
        hour = datetime.now().hour
        energy_drain = 0.05 if (6 <= hour < 22) else 0.15
        if self.state == "sleep":
            self.energy = min(100, self.energy + dt * 0.5)
            self.hunger = max(0, self.hunger - dt * 0.3)
        else:
            self.energy = max(0, self.energy - dt * energy_drain)
        if self.mood > 50: self.mood -= dt * 0.02
        elif self.mood < 50: self.mood += dt * 0.01
        self.control_panel.update_status_text(self.hunger, self.energy, self.mood, self.affection)

    def toggle_pause(self): self.is_paused = not self.is_paused

    def start_drag(self):
        if not self.is_dragging:
            self.is_dragging = True
            self.state = "drag"
            self.is_belly_up = self.is_nuzzling = False
            self.update_image()

    def setup_global_mouse_listener(self):
        self.last_click_time = 0
        self.last_click_pos = None
        def on_click(x, y, button, pressed):
            if pressed:
                if self.is_nuzzling: self.stop_nuzzle()
                self.is_belly_up = False
                self.last_activity_time = time.time()
            if pressed and button == mouse.Button.left:
                curr = time.time()
                if curr - self.last_click_time < 0.4:
                    if self.last_click_pos and math.hypot(x-self.last_click_pos[0], y-self.last_click_pos[1]) < 10:
                        self.signals.double_clicked.emit()
                        self.last_click_time = 0 
                        return
                self.last_click_time, self.last_click_pos = curr, (x, y)
        
        def on_move(x, y):
            if self.is_nuzzling:
                fox_cheek_x = self.x() + self.width() 
                fox_cheek_y = self.y() + int(self.height() * 0.4)
                dist = math.hypot(x - fox_cheek_x, y - fox_cheek_y)
                if dist > 20: 
                    self.stop_nuzzle()
            else:
                self.last_activity_time = time.time()

        self.mouse_listener = mouse.Listener(on_click=on_click, on_move=on_move)
        self.mouse_listener.start()

    def stop_nuzzle(self):
        if self.is_nuzzling:
            self.is_nuzzling = False
            # 先更新狀態與影格
            self.state = "notice"
            self.mood = min(100, self.mood + 5)
            self.frame_index = 0  
            # 立即執行一次圖片更新
            self.update_image()
            self.last_activity_time = time.time()
            # 稍微增加一點驚嚇停留時間，防止立刻進入 walk 導致的連續 resize 破圖
            QTimer.singleShot(1000, self.set_random_target)

    def handle_global_double_click(self):
        target = QCursor.pos()
        if self.geometry().contains(target): return
        self.is_paused = self.is_nuzzling = self.is_belly_up = False
        self.state, self.speed = "notice", 30
        self.frame_index = 0 
        self.update_image()
        self.target_pos = QPoint(target.x() - self.width() // 2, target.y() - self.height() // 2)
        QTimer.singleShot(200, lambda: self._start_chase())

    def _start_chase(self):
        if not self.is_dragging: self.state = "walk"

    def update_image(self):
        try:
            frames = self.assets.get(self.state, self.assets["idle"])
            self.frame_index %= len(frames)
            raw_pixmap = QPixmap(frames[self.frame_index])
            if raw_pixmap.isNull(): return
            
            old_rect = self.geometry()
            base_h = 150 
            if self.state in ["fall"]: h = max(1, int(base_h * 1.3 * self.scale_factor))
            elif self.state in ["drag"]: h = max(1, int(base_h * 1.5 * self.scale_factor))
            elif self.state in ["belly"]: h = max(1, int(base_h * 0.75 * self.scale_factor)) 
            elif self.state in ["sleep"]: h = max(1, int(base_h * 1.15 * self.scale_factor))
            else: h = max(1, int(base_h * self.scale_factor))
            
            pixmap = raw_pixmap.scaledToHeight(h, Qt.TransformationMode.SmoothTransformation)
            
            # --- 顏色替換邏輯 ---
            if self.tint_color:
                img = pixmap.toImage()
                target_h, target_s, target_l, _ = self.tint_color.getHsl()

                for y in range(img.height()):
                    for x in range(img.width()):
                        c = img.pixelColor(x, y)
                        if c.alpha() < 200:  # 
                            continue
                        if c.alpha() == 0:  
                            continue

                        orig_h, orig_s, orig_l, orig_a = c.getHsl()

                        # 只選橘紅毛皮
                        is_orange_fur = (
                            (orig_h <= 38 or orig_h >= 345) and
                                orig_s > 85 and
                                95 < orig_l < 228
                        )

                        if is_orange_fur:
                            # 亮度直接保留原值，只換色相與飽和度
                            # 這樣光影細節完全保留，不會因基準值偏差導致顏色失真
                            fur_l_min, fur_l_max = 95, 228
                            ratio = (orig_l - fur_l_min) / (fur_l_max - fur_l_min)
                            ratio = max(0.0, min(1.0, ratio))

                            if target_s < 20:
                                # 目標色幾乎無飽和（白/灰/黑），依照目標亮度 (target_l) 重新映射
                                # 允許亮度達到 255，這樣選白色時就能呈現純白毛皮並保留陰影
                                tgt_l_min = max(10, target_l - 50)
                                tgt_l_max = min(255, target_l + 40)
                                final_l = int(tgt_l_min + ratio * (tgt_l_max - tgt_l_min))
                                img.setPixelColor(x, y, QColor.fromHsl(0, 0, final_l, orig_a))
                            else:
                                # 有色相：把原圖亮度範圍映射到目標色亮度附近
                                tgt_l_min = max(10, target_l - 50)
                                tgt_l_max = min(245, target_l + 50)
                                final_l = int(tgt_l_min + ratio * (tgt_l_max - tgt_l_min))
                                img.setPixelColor(x, y, QColor.fromHsl(target_h, target_s, final_l, orig_a))

                pixmap = QPixmap.fromImage(img)

            if self.state == "nuzzle": self.direction = 1
            if self.direction == -1 and self.state not in ["front_idle", "pet", "belly", "eat"]:
                pixmap = pixmap.transformed(QTransform().scale(-1, 1), Qt.TransformationMode.SmoothTransformation)
            
            self.label.setPixmap(pixmap)
            
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setFixedSize(pixmap.size()) 
            self.setMask(pixmap.mask()) 
            
            if old_rect.width() > 0 and self.state not in ["drag", "fall", "nuzzle"]:
                self.move(old_rect.x() + old_rect.width()//2 - self.width()//2, 
                          old_rect.y() + old_rect.height() - self.height())
        except Exception:
            pass

    def pet_logic(self):
        if self.is_dragging or self.is_paused: return
        self.update_model_stats()
        now = time.time()
        idle_time = now - self.last_activity_time

        if self.state == "sleep" and self.energy >= 99 and self.hunger <= 1:
            self.state, self.frame_index = "idle", 0

        if self.state == "nuzzle":
            cursor = QCursor.pos()
            new_x = cursor.x() - self.width()
            new_y = cursor.y() - int(self.height() * 0.4)
            self.move(new_x, new_y)
            if now - self.nuzzle_start_time > 30: self.stop_nuzzle()
            self._update_frame_logic(now)
            return

        if self.state == "fall":
            self.move(self.x(), self.y() + 20)
            self.fall_counter += 1
            if self.fall_counter > 12: 
                self.fall_counter = 0
                self.set_random_target()
            self.update_image()
            return

        if ((idle_time > 100 or (self.mood < 40 and random.random() < 0.05)) and 
            self.state not in ["walk", "sleep", "eat"] and
            not self.is_belly_up and not self.is_nuzzling):
            cursor = QCursor.pos()
            self.target_pos = QPoint(cursor.x() - self.width(), cursor.y() - int(self.height() * 0.4))
            self.state, self.speed = "walk", 30 
        
        cursor_local = self.mapFromGlobal(QCursor.pos())
        is_hovering = self.rect().contains(cursor_local)
        is_upper = is_hovering and cursor_local.y() < self.height() // 2
        if is_hovering and self.state not in ["drag", "nuzzle", "eat"]:
            if not self.is_user_intending_pet:
                self.is_user_intending_pet, self.pet_intent_start_time = True, now
            elif now - self.pet_intent_start_time > 1.0:
                if is_upper:
                    if not self.is_being_petted:
                        self.is_being_petted, self.mood, self.affection = True, min(100, self.mood + 2), self.affection + 0.5
                        self.pet_touch_start_time = now
                        if not self.is_belly_up: self.state = "pet"
                    self.mood, self.affection = min(100, self.mood + 0.3), self.affection + 0.1
                    if not self.is_belly_up and (now - self.pet_touch_start_time > 10):
                        self.is_belly_up, self.mood, self.state, self.frame_index = True, min(100, self.mood + 10), "belly", 0
                else:
                    if self.is_being_petted:
                        self.is_being_petted = False
                        if not self.is_belly_up: self.state = "idle"
        else:
            self.is_user_intending_pet = False
            if self.is_being_petted:
                self.is_being_petted = False
                if not self.is_belly_up: self.state = "idle"

        if not is_hovering and (self.is_being_petted or self.is_belly_up):
            self.is_being_petted = self.is_belly_up = False
            self.state = "idle"

        self._update_frame_logic(now)

    def _update_frame_logic(self, now):
        idle_time = now - self.last_activity_time
        should_update_frame = True
        if self.state == "walk":
            self.move_towards_target()
            if idle_time > 30 or self.mood < 40:
                cursor = QCursor.pos()
                cheek_x = self.pos().x() + self.width()
                cheek_y = self.pos().y() + int(self.height() * 0.4)
                dist = math.hypot(cheek_x - cursor.x(), cheek_y - cursor.y())
                if dist < 25: 
                    self.state, self.is_nuzzling, self.nuzzle_start_time, self.frame_index = "nuzzle", True, now, 0
        elif self.state in ["sleep", "nuzzle", "pet", "belly", "eat"]:
            should_update_frame = False
            self.slow_tick_counter += 1
            if self.slow_tick_counter >= self.slow_anim_vector:
                self.slow_tick_counter, should_update_frame = 0, True
        elif self.state in ["idle", "front_idle"]:
            if not self.is_being_petted and not self.is_belly_up:
                r = random.random()
                if self.hunger >= 100 or (self.energy < 15 and r < 0.05) or (self.hunger > 80 and r < 0.05): 
                    self.state, self.frame_index = "sleep", 0
                elif r < 0.02: self.set_random_target()
                elif r < (0.02 + (self.mood / 5000)): 
                    self.state = "front_idle" if self.state == "idle" else "idle"
                    self.frame_index = 0
        if should_update_frame:
            frames = self.assets.get(self.state, self.assets["idle"])
            self.frame_index = (self.frame_index + 1) % len(frames)
            self.update_image()

    def set_random_target(self):
        self.state, self.is_belly_up, self.frame_index = "walk", False, 0
        geo = QApplication.primaryScreen().availableGeometry()
        tx, ty = random.randint(0, geo.width()-self.width()), random.randint(0, geo.height()-self.height())
        self.target_pos, self.speed = QPoint(tx, ty), self.normal_speed 

    def move_towards_target(self):
        curr = self.pos()
        diff = self.target_pos - curr
        dist = math.sqrt(diff.x()**2 + diff.y()**2)
        if dist < 15:
            self.state, self.speed = "idle", self.normal_speed
            return
        ratio = self.speed / dist
        self.direction = 1 if diff.x() > 0 else -1
        self.move(curr.x() + int(diff.x() * ratio), curr.y() + int(diff.y() * ratio))

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_timer.stop()  
            self.is_local_double_clicking = True  
            self.is_paused = self.is_nuzzling = self.is_belly_up = False
            self.state, self.speed, self.frame_index = "notice", 25, 0
            self.update_image()
            target = QCursor.pos()
            self.target_pos = QPoint(target.x() - self.width() // 2, target.y() - self.height() // 2)
            QTimer.singleShot(200, lambda: self._start_chase())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_timer.start(200)  
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.is_dragging: self.move(event.globalPosition().toPoint() - self.drag_start_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.click_timer.stop()
            if self.is_dragging:
                self.is_dragging = False
                self.state = "fall" 
            elif self.is_local_double_clicking:
                self.is_local_double_clicking = False

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: white; border: 1px solid gray; }")
        menu.addAction("🛠️ 狐狸狀態", self.control_panel.show)
        menu.addAction("📍 過來這裡", self.move_to_mouse)
        menu.addAction("🍖 餵食", self.feed_fox) 
        menu.addSeparator()
        menu.addAction("❌ 讓狐狸休息", QApplication.instance().quit)
        menu.exec(event.globalPos())

    def move_to_mouse(self):
        self.is_paused = self.is_nuzzling = self.is_belly_up = False
        target = QCursor.pos()
        self.target_pos = QPoint(target.x() - self.width() // 2, target.y() - self.height() // 2)
        self.speed, self.state = 15, "walk"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = FoxPet()
    sys.exit(app.exec())

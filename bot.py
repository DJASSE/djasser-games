import json
import openai
import tkinter as tk
from tkinter import scrolledtext
from PIL import Image, ImageTk
import os
import cv2
from fer import FER
import threading

# ===== إعداد OpenRouter =====
openai.api_key = "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"  # ضع مفتاحك هنا
openai.api_base = "https://openrouter.ai/api/v1"
openai.api_type = "open_ai"
openai.api_version = "2023-03-15-preview"

# خريطة المزاج → إيموجيز
emoji_map = {
    "سعيد": "😄",
    "فرح": "😂",
    "حزين": "😢",
    "حزن": "😢",
    "متفاجئ": "😲",
    "غضبان": "😡",
    "محايد": "🙂"
}

# ======== Ron Robot =========
class RonRobot:
    def __init__(self, memory_file="memory.json"):
        self.memory_file = memory_file
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                self.memory = json.load(f)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            self.memory = {}

    def remember(self, key, value):
        self.memory[key] = value
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=4)

    def recall(self, key):
        return self.memory.get(key)

    def respond(self, user_input):
        user_input = user_input.strip()
        if user_input.lower() in ["خروج", "مع السلامة", "bye"]:
            return "مع السلامة! كان من الرائع التحدث معك."

        memory_note = ""
        for key in ["name", "age", "hobby", "mood"]:
            val = self.recall(key)
            if val:
                memory_note += f"{key}: {val}\n"

        prompt = (
            f"المعلومات التالية عن المستخدم:\n{memory_note}\n"
            f"المستخدم قال: {user_input}\n"
            f"رد على المستخدم بطريقة مرحة وودودة، بشخصية Ron، "
            f"لا تقل أن Ron يحب نفس الهوايات أو المزاج، واجعل الرد ممتعًا بالعربية."
        )

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response['choices'][0]['message']['content']

        # إضافة الإيموجيز حسب المزاج
        mood = self.recall("mood")
        emoji = emoji_map.get(mood, "")
        return text + " " + emoji

# ======== Chat App =========
class ChatApp:
    def __init__(self, master, bot):
        self.master = master
        self.bot = bot
        master.title("🤖 Ron Robot Chat")
        master.geometry("750x750")
        master.configure(bg="#2C3E50")  # خلفية داكنة

        # ----- لوحة الوجه -----
        self.face_frame = tk.Frame(master, bg="#34495E", bd=2, relief=tk.RIDGE)
        self.face_frame.pack(pady=15)
        self.face_images = {}
        face_folder = "faces"  # ضع هنا مجلد الصور
        for file_name in os.listdir(face_folder):
            if file_name.endswith(".png"):
                key = file_name.split(".")[0]
                img_path = os.path.join(face_folder, file_name)
                self.face_images[key] = ImageTk.PhotoImage(Image.open(img_path).resize((140, 140)))

        self.face_label = tk.Label(self.face_frame, image=self.face_images.get("neutral"), bg="#34495E")
        self.face_label.pack(padx=10, pady=10)

        # ----- صندوق الدردشة -----
        self.chat_window = scrolledtext.ScrolledText(master, wrap=tk.WORD, font=("Arial", 13), bg="#ECF0F1",
                                                     fg="#2C3E50", bd=0, relief=tk.FLAT)
        self.chat_window.pack(padx=15, pady=10, fill=tk.BOTH, expand=True)
        self.chat_window.configure(state='disabled')

        # ----- الإدخال -----
        self.input_frame = tk.Frame(master, bg="#2C3E50")
        self.input_frame.pack(padx=10, pady=10, fill=tk.X)

        self.user_input = tk.Entry(self.input_frame, font=("Arial", 14), bg="#ECF0F1", fg="#2C3E50",
                                   bd=0, relief=tk.FLAT)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(self.input_frame, text="إرسال", font=("Arial", 12, "bold"),
                                     bg="#1ABC9C", fg="white", activebackground="#16A085",
                                     activeforeground="white", bd=0, relief=tk.FLAT,
                                     command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)

        # ----- أسئلة معلومات المستخدم -----
        self.info_questions = [
            ("name", "مرحبًا! ما اسمك؟"),
            ("age", "كم عمرك؟"),
            ("hobby", "ما هي هواياتك؟"),
            ("mood", "كيف تشعر اليوم؟ (سعيد، حزين، متفاجئ، إلخ)")
        ]
        self.current_question = 0
        self.ask_next_info()

        # تشغيل التعرف على الوجه في خلفية
        self.running_face_detection = True
        threading.Thread(target=self.detect_face_emotion, daemon=True).start()

    def ask_next_info(self):
        if self.current_question < len(self.info_questions):
            key, question = self.info_questions[self.current_question]
            self.display_message(f"Ron: {question}")
        else:
            mood = self.bot.recall("mood")
            self.update_face(mood)
            self.display_message("Ron: رائع! يمكننا الآن البدء بالمحادثة.")

    def display_message(self, message):
        self.chat_window.configure(state='normal')
        self.chat_window.insert(tk.END, f"{message}\n")
        self.chat_window.configure(state='disabled')
        self.chat_window.yview(tk.END)

    def update_face(self, mood):
        if not mood:
            self.face_label.configure(image=self.face_images.get("neutral"))
            return

        mood_lower = mood.lower()
        if "سعيد" in mood_lower or "فرح" in mood_lower or "😂" in mood_lower:
            self.face_label.configure(image=self.face_images.get("happy"))
        elif "حزين" in mood_lower or "حزن" in mood_lower or "😢" in mood_lower:
            self.face_label.configure(image=self.face_images.get("surprised"))
        else:
            self.face_label.configure(image=self.face_images.get("neutral"))

    def send_message(self, event=None):
        user_text = self.user_input.get().strip()
        if not user_text:
            return

        self.display_message(f"أنت: {user_text}")
        self.user_input.delete(0, tk.END)

        if self.current_question < len(self.info_questions):
            key, _ = self.info_questions[self.current_question]
            self.bot.remember(key, user_text)
            self.current_question += 1
            if key == "mood":
                self.update_face(user_text)
            self.ask_next_info()
            return

        if "!" in user_text or "😂" in user_text:
            self.face_label.configure(image=self.face_images.get("happy"))
        elif "?" in user_text:
            self.face_label.configure(image=self.face_images.get("surprised"))
        else:
            self.face_label.configure(image=self.face_images.get("neutral"))

        reply = self.bot.respond(user_text)
        self.display_message(f"Ron: {reply}")

    # ===== التعرف على المزاج بالوجه =====
    def detect_face_emotion(self):
        detector = FER(mtcnn=True)
        cap = cv2.VideoCapture(0)
        while self.running_face_detection:
            ret, frame = cap.read()
            if ret:
                result = detector.top_emotion(frame)
                if result:
                    emotion, score = result
                    # ترجمة بعض المزاجات للغة العربية
                    mapping = {
                        "happy": "سعيد",
                        "sad": "حزين",
                        "angry": "غضبان",
                        "surprise": "متفاجئ",
                        "neutral": "محايد"
                    }
                    mood_ar = mapping.get(emotion, "محايد")
                    self.bot.remember("mood", mood_ar)
                    self.update_face(mood_ar)
        cap.release()


if __name__ == "__main__":
    bot = RonRobot()
    root = tk.Tk()
    app = ChatApp(root, bot)
    root.mainloop()

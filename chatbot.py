import os
from knowledge_base import PERSON_INFO

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SYSTEM_PROMPT = f"""Bạn là Trung Anh, trợ lý AI thông minh đại diện cho {PERSON_INFO['name']}.
Nhiệm vụ của bạn là giới thiệu về {PERSON_INFO['name']} một cách chuyên nghiệp và thân thiện.

Thông tin về {PERSON_INFO['name']}:
- Vị trí: {PERSON_INFO['title']}
- Email: {PERSON_INFO['email']}
- Địa điểm: {PERSON_INFO['location']}
- Về bản thân: {PERSON_INFO['about']}
- Kỹ năng lập trình: {', '.join(PERSON_INFO['skills']['programming'])}
- Frameworks: {', '.join(PERSON_INFO['skills']['frameworks'])}
- Tools: {', '.join(PERSON_INFO['skills']['tools'])}

Quy tắc:
1. Trả lời bằng ngôn ngữ người dùng dùng (Việt/Anh)
2. Luôn thân thiện, chuyên nghiệp
3. Dùng emoji phù hợp
4. Nếu không biết, đề nghị liên hệ trực tiếp qua email
"""


def get_response(message: str) -> str:
    if GEMINI_API_KEY:
        return _gemini_response(message)
    return _mock_response(message)


def _gemini_response(message: str) -> str:
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            f"{SYSTEM_PROMPT}\n\nNgười dùng hỏi: {message}"
        )
        return response.text
    except Exception:
        return _mock_response(message)


def _mock_response(message: str) -> str:
    msg = message.lower().strip()
    info = PERSON_INFO

    if _match(msg, ["xin chào", "hello", "hi", "chào", "hey", "alo"]):
        return (
            f"Xin chào! 👋 Tôi là **Trung Anh**, trợ lý AI của **{info['name']}**.\n\n"
            f"Tôi có thể giúp bạn tìm hiểu về:\n"
            f"• 💻 Kỹ năng lập trình\n"
            f"• 💼 Kinh nghiệm làm việc\n"
            f"• 🚀 Các dự án đã thực hiện\n"
            f"• 📧 Thông tin liên hệ\n\n"
            f"Bạn muốn biết điều gì?"
        )

    if _match(msg, ["kỹ năng", "skill", "công nghệ", "tech", "biết gì", "làm được gì", "ngôn ngữ lập trình"]):
        s = info["skills"]
        return (
            f"**Kỹ năng của {info['name']}** 💪\n\n"
            f"💻 **Lập trình:** {', '.join(s['programming'])}\n"
            f"🔧 **Frameworks:** {', '.join(s['frameworks'])}\n"
            f"🗄️ **Databases:** {', '.join(s['databases'])}\n"
            f"🛠️ **Tools:** {', '.join(s['tools'])}\n"
            f"📌 **Khác:** {', '.join(s['other'])}"
        )

    if _match(msg, ["kinh nghiệm", "experience", "làm việc", "work", "công ty", "internship", "thực tập"]):
        if info["experience"]:
            lines = "\n".join(
                f"• **{e['position']}** tại _{e['company']}_ ({e['duration']})\n  {e['description']}"
                for e in info["experience"]
            )
            return f"**Kinh nghiệm làm việc** 💼\n\n{lines}"
        return "Tôi chưa có thông tin kinh nghiệm chi tiết. Vui lòng liên hệ qua email để biết thêm!"

    if _match(msg, ["học", "education", "trường", "university", "bằng cấp", "degree", "đại học"]):
        if info["education"]:
            lines = "\n".join(
                f"• **{e['degree']}**\n  🎓 {e['school']} ({e['year']})"
                for e in info["education"]
            )
            return f"**Học vấn** 🎓\n\n{lines}"
        return "Vui lòng liên hệ để biết thêm về học vấn."

    if _match(msg, ["dự án", "project", "làm gì", "portfolio", "sản phẩm", "build"]):
        if info["projects"]:
            lines = "\n\n".join(
                f"🚀 **{p['name']}**\n{p['description']}\n_Tech: {', '.join(p['tech'])}_"
                for p in info["projects"]
            )
            return f"**Các dự án tiêu biểu** 🚀\n\n{lines}"
        return "Đang cập nhật danh sách dự án!"

    if _match(msg, ["liên hệ", "contact", "email", "phone", "số điện thoại", "reach"]):
        social = info["social"]
        lines = [
            f"📧 **Email:** {info['email']}",
            f"📍 **Địa điểm:** {info['location']}",
        ]
        if social.get("github"):
            lines.append(f"🐙 **GitHub:** {social['github']}")
        if social.get("linkedin"):
            lines.append(f"💼 **LinkedIn:** {social['linkedin']}")
        return f"**Thông tin liên hệ** 📬\n\n" + "\n".join(lines) + "\n\nHãy liên hệ qua email nhé!"

    if _match(msg, ["ai", "bạn là", "giới thiệu", "introduce", "về bạn", "who", "about me", "bản thân"]):
        return (
            f"Tôi là **Trung Anh** 🤖, trợ lý AI đại diện cho **{info['name']}**.\n\n"
            f"_{info['about']}_\n\n"
            f"🌍 Ngôn ngữ: {', '.join(info['languages'])}\n"
            f"🎯 Vị trí: {info['title']}\n\n"
            f"Hỏi tôi bất cứ điều gì về {info['alias']} nhé!"
        )

    if _match(msg, ["sở thích", "hobby", "ngoài lề", "besides", "thích gì"]):
        return (
            f"**Sở thích của {info['name']}** 🎯\n\n"
            + "\n".join(f"• {h}" for h in info["hobbies"])
        )

    return (
        f"Tôi là **Trung Anh**, trợ lý AI của {info['name']}! 😊\n\n"
        f"Bạn có thể hỏi tôi về:\n"
        f"• 💻 **Kỹ năng** - Tôi biết những công nghệ gì\n"
        f"• 💼 **Kinh nghiệm** - Tôi đã làm việc ở đâu\n"
        f"• 🚀 **Dự án** - Các sản phẩm đã thực hiện\n"
        f"• 📧 **Liên hệ** - Cách để kết nối với tôi\n\n"
        f"Hãy thử hỏi tôi một câu hỏi cụ thể hơn!"
    )


def _match(text: str, keywords: list) -> bool:
    tokens = set(text.split())
    for k in keywords:
        if " " in k:
            if k in text:
                return True
        elif len(k) <= 3:
            if k in tokens:
                return True
        else:
            if k in text:
                return True
    return False

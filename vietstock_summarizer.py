import os
import requests
import xml.etree.ElementTree as ET
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
from datetime import datetime

# Configure Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Email configuration
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# RSS Feeds to scrape
RSS_FEEDS = {
    "Chứng khoán": "https://vietstock.vn/144/chung-khoan.rss",
    "Doanh nghiệp": "https://vietstock.vn/733/doanh-nghiep.rss",
    "Tài chính": "https://vietstock.vn/734/tai-chinh.rss",
    "Bất động sản": "https://vietstock.vn/762/bat-dong-san.rss",
}

def fetch_rss_feed(url, category, max_items=5):
    """Fetches and parses an RSS feed, returning a list of news titles and links."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall('.//item')[:max_items]:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            if title:
                items.append({'title': title, 'link': link, 'category': category})
        return items
    except Exception as e:
        print(f"Error fetching feed {url}: {e}")
        return []

def summarize_with_gemini(news_items):
    """Uses Gemini API to summarize the news."""
    if not GEMINI_API_KEY:
         return "Lỗi: Chưa cấu hình GEMINI_API_KEY."
    
    if not news_items:
        return "Không có tin tức nào được tìm thấy hôm nay."

    prompt = "Bạn là một chuyên gia phân tích tài chính cá nhân. Dưới đây là danh sách các tin tức mới nhất từ Vietstock.\n" \
             "Nhiệm vụ của bạn là viết một bản tin tổng hợp ngắn gọn, dễ hiểu, nêu bật các sự kiện quan trọng nhất ảnh hưởng tới thị trường. " \
             "Phân chia nội dung theo các chuyên mục nếu cần. " \
             "Cuối bản tin, hãy thêm 1-2 câu nhận định ngắn (từ góc độ AI) về thị trường hôm nay.\n\n"
    
    for item in news_items:
        prompt += f"- [{item['category']}] {item['title']}\n"
    
    try:
        # Sử dụng model Gemini 2.5 Flash
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
         print(f"Error calling Gemini API: {e}")
         return "Lỗi khi gọi AI tóm tắt. Tuy nhiên, bạn vẫn có thể xem danh sách tiêu đề gốc bên dưới."

def send_email(subject, body, news_items):
    """Sends an email via Gmail SMTP."""
    if not all([GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECEIVER_EMAIL]):
        print("Missing email configuration (GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RECEIVER_EMAIL). Cannot send email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"Vietstock AI Bot <{GMAIL_ADDRESS}>"
    msg['To'] = RECEIVER_EMAIL

    # Create HTML version
    html_body = f"<h2>{subject}</h2>"
    html_body += f"<div style='font-family: Arial, sans-serif; line-height: 1.6; color: #333;'>"
    
    # Process markdown-like response from Gemini to basic HTML
    processed_body = body.replace("\n\n", "<br><br>").replace("**", "<b>").replace("\n", "<br>")
    
    html_body += f"<div style='background-color: #f0f7ff; padding: 15px; border-left: 4px solid #0056b3; margin-bottom: 20px; border-radius: 4px;'>{processed_body}</div>"
    html_body += "<h3>📰 Danh sách bài báo gốc (Click để đọc chi tiết):</h3><ul>"
    for item in news_items:
        html_body += f"<li style='margin-bottom: 5px;'><b>[{item['category']}]</b> <a href='{item['link']}' style='color: #0056b3; text-decoration: none;'>{item['title']}</a></li>"
    html_body += "</ul><br><hr><p style='font-size: 12px; color: #888;'>Email này được tạo và gửi tự động bởi AI.</p></div>"

    part1 = MIMEText(body + "\n\nDanh sách bài báo:\n" + "\n".join([f"- {i['title']} ({i['link']})" for i in news_items]), 'plain')
    part2 = MIMEText(html_body, 'html')

    msg.attach(part1)
    msg.attach(part2)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email sent successfully to", RECEIVER_EMAIL)
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    today_str = datetime.now().strftime("%d/%m/%Y")
    print(f"Bắt đầu tổng hợp tin tức Vietstock ngày {today_str}...")
    
    all_news = []
    for category, url in RSS_FEEDS.items():
        print(f"Đang lấy tin mục {category}...")
        news = fetch_rss_feed(url, category)
        all_news.extend(news)
        
    print(f"Tổng cộng lấy được {len(all_news)} tin bài.")
    if not all_news:
        print("Không có tin nào. Dừng tại đây.")
        return

    print("Bắt đầu nhờ AI (Gemini) tóm tắt...")
    summary = summarize_with_gemini(all_news)
    
    print("AI đã tóm tắt xong. Đang gửi email...")
    email_subject = f"📊 Bản tin tóm tắt Vietstock tự động ngày {today_str}"
    send_email(email_subject, summary, all_news)
    print("Tiến trình hoàn tất!")

if __name__ == "__main__":
    main()

import smtplib
from email.mime.text import MIMEText

msg = MIMEText('Test email from ERP')
msg['Subject'] = 'ERP Test Mail'
msg['From'] = 'krunalchandi.hcp@gmail.com'
msg['To'] = 'krunalchandi.hcp@gmail.com'

try:
    with smtplib.SMTP('smtp.gmail.com', 587) as s:
        s.ehlo()
        s.starttls()
        s.login('krunalchandi.hcp@gmail.com', 'qrcfnyawxvlwjgvk')
        s.sendmail('krunalchandi.hcp@gmail.com', 'krunalchandi.hcp@gmail.com', msg.as_string())
        print('Mail sent successfully!')
except Exception as e:
    print(f'Error: {e}')

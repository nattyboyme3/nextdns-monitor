import dotenv
import sys
import pytz
import nextdns_logs
import os
import logging
import pandas as pd
from dataclasses import asdict
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

def main(args):
    dotenv.load_dotenv()
    fetcher =  nextdns_logs.NextDNSLogFetcher(os.environ["API_KEY"], os.environ.get("PROFILE_ID"))
    critical_categories = os.environ.get("CRITICAL_CATEGORIES", "").split(",")
    warning_domains = os.environ.get("WARNING_DOMAINS", "").split(",")
    timezone_str = os.environ.get("TIMEZONE", "America/New_York")
    timezone = pytz.timezone(timezone_str)
    try:
        yesterday_logs = fetcher.fetch_logs_for_previous_day(per_page=500, tz=timezone)
        logger.info(f"Fetched {len(yesterday_logs)} logs from previous day.")
        df = pd.DataFrame([asdict(l) for l in yesterday_logs])
        critical_results = df[df['reason_name'].isin(critical_categories)]
        critical_info = (critical_results.groupby(["reason_name", "device_name", "root"])
                       .agg(first_seen=("timestamp", "min"),
                            last_seen=("timestamp", "max"),
                            count=("timestamp", "size"))
                       .reset_index())
        critical_info["first_seen"] = pd.to_datetime(critical_info["first_seen"])
        critical_info["last_seen"] = pd.to_datetime(critical_info["last_seen"])
        critical_info = critical_info.assign(
            first_seen=lambda x: x.first_seen.dt.tz_convert(timezone_str),
            last_seen=lambda x: x.last_seen.dt.tz_convert(timezone_str),
        )
        warning_results = df[df["root"].isin(warning_domains)]
        warning_info = (warning_results.groupby([ "device_name", "root"])
                        .agg(first_seen=("timestamp", "min"),
                             last_seen=("timestamp", "max"),
                             count=("timestamp", "size"))
                        .reset_index())
        warning_info["first_seen"] = pd.to_datetime(warning_info["first_seen"])
        warning_info["last_seen"] = pd.to_datetime(warning_info["last_seen"])
        warning_info = warning_info.assign(
            first_seen=lambda x: x.first_seen.dt.tz_convert(timezone_str),
            last_seen=lambda x: x.last_seen.dt.tz_convert(timezone_str),
        )
        notify_if_necessary(critical_info, warning_info)
    finally:
        fetcher.close()


def notify_if_necessary(critical_info, warning_info):
    subject = None
    email_lines = []
    if not critical_info.empty:
        logger.info("Notifications to send:")
        email_lines = ["The following requests in NextDNS are suspicious and you might want to discuss them: "]
        subject = "🔴NextDNS Suspicious Activity Detected"
        for _, row in critical_info.iterrows():
            line = (f"- {row['count']}x hits on domain {row['root']} "
                    f"in category '{row['reason_name']}' "
                    f"on device {row['device_name']} "
                    f"between {row['first_seen'].strftime('%m/%d, %H:%M')} "
                    f"and {row['last_seen'].strftime('%m/%d, %H:%M')}")
            logger.info(line)
            email_lines.append(line)
    if not warning_info.empty:
        email_lines.append("\nThe following requests were flagged as warnings:")
        if not subject:
            subject = "🟠NextDNS Warnings Detected"
        for _, row in warning_info.iterrows():
            line = (f"- {row['count']}x hits on monitored domain {row['root']} "
                    f"on device {row['device_name']} "
                    f"between {row['first_seen'].strftime('%m/%d, %H:%M')} "
                    f"and {row['last_seen'].strftime('%m/%d, %H:%M')}")
            logger.info(line)
            email_lines.append(line)
    if not subject:
        email_lines = ["No notifications about NextDNS activity for yesterday."]
        logger.info("No notifications to send.")
        subject = "🟢No Suspicious NextDNS Activity"
    msg = EmailMessage()
    msg["From"] = os.environ.get("FROM_EMAIL")
    msg["To"] = os.environ.get("TO_EMAIL")
    msg["Subject"] = subject
    msg.set_content("\n".join(email_lines))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(os.environ.get("FROM_EMAIL"), os.environ.get("APP_PASSWORD"))  # use app password
        s.send_message(msg)


if __name__ == "__main__":
    main(sys.argv[1:])
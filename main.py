import dotenv
import sys
import pytz
from pandas import DataFrame

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
    gap_minute_threshold = int(os.environ.get("GAP_MINUTE_THRESHOLD", "60"))
    timezone = pytz.timezone(timezone_str)
    try:
        yesterday_logs = fetcher.fetch_logs_for_previous_day(per_page=500, tz=timezone)
        logger.info(f"Fetched {len(yesterday_logs)} logs from previous day.")
        df = pd.DataFrame([asdict(l) for l in yesterday_logs])
        critical_results = df[df['reason_name'].isin(critical_categories)]
        critical_info = process_result_info(critical_results, ["reason_name", "device_name", "root"], timezone_str)
        warning_results = df[df["root"].isin(warning_domains)]
        warning_info = process_result_info(warning_results,[ "device_name", "root"], timezone_str)
        gap_info = gap_analysis(df, timezone, threshold_minutes=gap_minute_threshold)
        notify_if_necessary(critical_info, warning_info, gap_info, df)
    finally:
        fetcher.close()


def process_result_info(result_info: pd.DataFrame, group_fields: list[str], timezone: str) -> pd.DataFrame:
    processed_info = (result_info.groupby(group_fields)
                      .agg(first_seen=("timestamp", "min"),
                           last_seen=("timestamp", "max"),
                           count=("timestamp", "size"))
                      .reset_index())
    processed_info["first_seen"] = pd.to_datetime(processed_info["first_seen"])
    processed_info["last_seen"] = pd.to_datetime(processed_info["last_seen"])
    processed_info = processed_info.assign(
        first_seen=lambda x: x.first_seen.dt.tz_convert(timezone),
        last_seen=lambda x: x.last_seen.dt.tz_convert(timezone),
    )
    return processed_info

def gap_analysis(logs: pd.DataFrame, timezone: pytz.BaseTzInfo, threshold_minutes: int = 60) -> pd.DataFrame:
    if logs.empty or "device_name" not in logs.columns:
        return pd.DataFrame(columns=["device_name", "gap_start", "gap_end", "gap_duration_minutes"])
    # Make a copy to avoid modifying the original
    logs = logs.copy()
    logs["timestamp"] = pd.to_datetime(logs["timestamp"])
    # Sort by device_name and timestamp
    logs = logs.sort_values(["device_name", "timestamp"]).reset_index(drop=True)
    # Calculate time differences and previous timestamp per device
    logs["time_diff"] = logs.groupby("device_name")["timestamp"].diff().dt.total_seconds().div(60).fillna(0)
    logs["prev_timestamp"] = logs.groupby("device_name")["timestamp"].shift(1)
    # Filter for gaps exceeding the threshold
    gaps = logs[logs["time_diff"] > threshold_minutes].copy()
    if gaps.empty:
        return pd.DataFrame(columns=["device_name", "gap_start", "gap_end", "gap_duration_minutes"])
    # Create gap columns with timezone conversion
    gaps["gap_start"] = pd.to_datetime(gaps["prev_timestamp"]).dt.tz_convert(timezone)
    gaps["gap_end"] = pd.to_datetime(gaps["timestamp"]).dt.tz_convert(timezone)
    gaps["gap_duration_minutes"] = gaps["time_diff"]

    return gaps[["device_name", "gap_start", "gap_end", "gap_duration_minutes"]]


def analyze_top_categories_and_sites(df: pd.DataFrame) -> str:
    """
    Analyzes the dataframe to find top 5 sites per device (excluding blocked requests).

    Returns a formatted string for inclusion in email notifications.
    """
    if df.empty:
        return "\n\n--- Usage Analytics ---\nNo data available for analysis."

    # Filter out blocked requests
    allowed_df = df[df['status'] != 'blocked'].copy()

    if allowed_df.empty:
        return "\n\n--- Usage Analytics ---\nNo allowed requests found."

    lines = ["\n\n--- Usage Analytics ---"]

    # Get unique devices
    devices = allowed_df['device_name'].unique()

    for device in sorted(devices):
        device_df = allowed_df[allowed_df['device_name'] == device]

        # Find top 5 sites for this device
        site_counts = device_df.groupby('root').size().sort_values(ascending=False).head(5)

        if site_counts.empty:
            continue

        # Format sites inline
        sites_str = ", ".join([f"{site}: {cnt}" for site, cnt in site_counts.items()])
        lines.append(f"\n{device}: {sites_str}")

    return "\n".join(lines)

def notify_if_necessary(critical_info: DataFrame, warning_info: DataFrame, gap_info: DataFrame, df: DataFrame):
    subject = None
    email_lines = []
    if not critical_info.empty:
        email_lines = ["The following requests in NextDNS are suspicious and you might want to discuss them: "]
        subject = "🔴NextDNS Suspicious Activity Detected"
        for _, row in critical_info.iterrows():
            line = (f"- {row['count']}x hits on domain {row['root']} "
                    f"in category '{row['reason_name']}' "
                    f"on device {row['device_name']} "
                    f"between {row['first_seen'].strftime('%m/%d, %H:%M')} "
                    f"and {row['last_seen'].strftime('%H:%M')}")
            email_lines.append(line)
    if not warning_info.empty:
        email_lines.append("\nThe following requests were flagged as warnings:")
        if not subject:
            subject = "🟠NextDNS Warnings Detected"
        for _, row in warning_info.iterrows():
            line = (f"- {row['count']}x hits on monitored domain {row['root']} "
                    f"on device {row['device_name']} "
                    f"between {row['first_seen'].strftime('%m/%d, %H:%M')} "
                    f"and {row['last_seen'].strftime('%H:%M')}")
            email_lines.append(line)
    if not gap_info.empty:
        email_lines.append("\nRequests stopped for a period of 60 minutes at the following time(s):")
        if not subject:
            subject = "🟠NextDNS Stoppages Detected"
        for _, row in gap_info.iterrows():
            line = (f"- {row['device_name']} sent no logs for {row['gap_duration_minutes']:.1f} minutes "
                    f"from {row['gap_start'].strftime('%m/%d, %H:%M')} "
                    f"to {row['gap_end'].strftime('%H:%M')}")
            email_lines.append(line)
    if not subject:
        email_lines = ["No notifications about NextDNS activity for yesterday."]
        subject = "🟢No Suspicious NextDNS Activity"

    # Add analytics section to all emails
    analytics_report = analyze_top_categories_and_sites(df)
    email_lines.append(analytics_report)

    [logger.info(x) for x in email_lines]
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
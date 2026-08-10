import anthropic
import subprocess

with open("/home/radxzi/.anthropic_key") as f:
    api_key = f.read().strip()

client = anthropic.Anthropic(api_key=api_key)

result = subprocess.run(
    ["sudo", "tail", "-n", "30", "/var/ossec/logs/alerts/alerts.log"],
    capture_output=True, text=True
)
recent_alert_text = result.stdout

if not recent_alert_text.strip():
    print("No recent alert data found.")
    exit()

message = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=300,
    messages=[
        {
            "role": "user",
            "content": f"""You are a SOC analyst assistant. Summarize the following raw Wazuh alert log data in plain English for a non-technical manager. Include: what happened, the source IP if present, the severity, whether it was automatically blocked, and a one-line recommendation.

Alert data:
{recent_alert_text}"""
        }
    ]
)

print("\n--- AI Alert Summary ---\n")
print(message.content[0].text)

import os
import sys
import time
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY2", "").strip("'\"")
URLSCAN_API_KEY = os.getenv("ScanIO_API_KEY", "").strip("'\"")
BOTOI_API_KEY = os.getenv("BOTOI_API_KEY", "").strip("'\"")

DATASET_PATH = os.path.join(PROJECT_ROOT, "database", "balanced_urls.csv")
OUTPUT_CSV = os.path.join(PROJECT_ROOT, "metricas_judge", "resultados_url_verifiers.csv")
REPORT_TXT = os.path.join(PROJECT_ROOT, "metricas_judge", "relatorio_url_verifiers.txt")

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

def check_safe_browsing(url):
    t0 = time.time()
    if not SAFE_BROWSING_API_KEY:
        return "ERROR_NO_KEY", time.time() - t0
    url_api = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
    payload = {
        "client": {"clientId": "spamapiproject", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}]
        }
    }
    params = {'key': SAFE_BROWSING_API_KEY}
    try:
        response = requests.post(url_api, params=params, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'matches' in data:
            return "MALICIOUS", time.time() - t0
        return "SAFE", time.time() - t0
    except requests.exceptions.RequestException as e:
        err_msg = ""
        if getattr(e, 'response', None) is not None:
            err_msg = f" - {e.response.text[:100].strip()}"
        return f"ERROR_{str(e)[:40]}{err_msg}", time.time() - t0
    except Exception as e:
        return f"ERROR_{str(e)[:50]}", time.time() - t0

def check_urlscan(url):
    t0 = time.time()
    if not URLSCAN_API_KEY:
        return "ERROR_NO_KEY", time.time() - t0
    
    headers = {"API-Key": URLSCAN_API_KEY}
    data = {"url": url, "visibility": "public"}
    
    try:
        # Submit new Scan
        submit_res = requests.post("https://urlscan.io/api/v1/scan/", headers=headers, json=data, timeout=10)
        if submit_res.status_code == 429:
            return "ERROR_RATELIMIT", time.time() - t0
        submit_res.raise_for_status()
        
        scan_uuid = submit_res.json().get("uuid")
        if not scan_uuid:
            return "ERROR_NO_UUID", time.time() - t0
            
        # Poll for result (can take 10-30 seconds)
        api_url = f"https://urlscan.io/api/v1/result/{scan_uuid}/"
        for _ in range(12): # Wait up to 60 seconds
            time.sleep(5)
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                result_data = res.json()
                verdicts = result_data.get("verdicts", {}).get("overall", {})
                if verdicts.get("malicious"):
                    return "MALICIOUS", time.time() - t0
                return "SAFE", time.time() - t0
            elif res.status_code == 404:
                # still processing
                continue
            else:
                res.raise_for_status()
                
        return "ERROR_TIMEOUT", time.time() - t0
    except requests.exceptions.RequestException as e:
        err_msg = ""
        if getattr(e, 'response', None) is not None:
            err_msg = f" - {e.response.text[:100].strip()}"
        return f"ERROR_{str(e)[:40]}{err_msg}", time.time() - t0
    except Exception as e:
        return f"ERROR_{str(e)[:50]}", time.time() - t0

def check_botoi(url):
    t0 = time.time()
    if not BOTOI_API_KEY:
        return "ERROR_NO_KEY", time.time() - t0
    api_url = "https://api.botoi.com/v1/phishing/check"
    headers = {"X-API-Key": BOTOI_API_KEY}
    try:
        response = requests.post(api_url, headers=headers, json={"url": url}, timeout=10)
        if response.status_code == 429:
            return "ERROR_RATELIMIT", time.time() - t0
        response.raise_for_status()
        data = response.json()
        
        is_phishing = False
        if "data" in data:
            d = data["data"]
            is_phishing = d.get("is_malicious") or d.get("isPhishing") or d.get("malicious") or d.get("phishing")
            if is_phishing is None and isinstance(d, dict):
                dump = json.dumps(d).lower()
                if "phishing\": true" in dump or "malicious\": true" in dump:
                    is_phishing = True
        
        if is_phishing:
            return "MALICIOUS", time.time() - t0
        return "SAFE", time.time() - t0
    except requests.exceptions.RequestException as e:
        err_msg = ""
        if getattr(e, 'response', None) is not None:
            err_msg = f" - {e.response.text[:100].strip()}"
        return f"ERROR_{str(e)[:40]}{err_msg}", time.time() - t0
    except Exception as e:
        return f"ERROR_{str(e)[:50]}", time.time() - t0

def generate_report(df, verifier_name, column_name, time_column):
    valid_df = df[df[column_name].isin(["MALICIOUS", "SAFE", "UNKNOWN"])]
    if valid_df.empty:
        return f"=== {verifier_name} ===\nNo valid results.\n\n"
    
    y_true = valid_df["true_label"].apply(lambda x: 1 if x == "MALICIOUS" else 0)
    y_pred = valid_df[column_name].apply(lambda x: 1 if x == "MALICIOUS" else 0)
    
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
    else:
        tn, fp, fn, tp = 0, 0, 0, 0
    
    unknowns = (valid_df[column_name] == "UNKNOWN").sum()
    errors = (df[column_name].str.startswith("ERROR")).sum()
    avg_time = df[time_column].mean()
    
    report = f"=== {verifier_name} ===\n"
    report += f"Accuracy:  {acc*100:.2f}%\n"
    report += f"Precision: {prec*100:.2f}%\n"
    report += f"Recall:    {rec*100:.2f}%\n"
    report += f"F1-Score:  {f1*100:.2f}%\n"
    report += f"Confusion Matrix: TP={tp}, FP={fp}, FN={fn}, TN={tn}\n"
    report += f"Average Time: {avg_time:.2f} seconds\n"
    report += f"Unknown/Unscanned: {unknowns}\n"
    report += f"Errors: {errors}\n\n"
    return report

def main():
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found: {DATASET_PATH}")
        sys.exit(1)
        
    print("Loading dataset...")
    df = pd.read_csv(DATASET_PATH)
    
    df['true_label'] = df['label'].apply(lambda x: "SAFE" if str(x).lower() == "benign" else "MALICIOUS")
    
    safe_samples = df[df['true_label'] == 'SAFE'].sample(n=500, random_state=42)
    malicious_samples = df[df['true_label'] == 'MALICIOUS'].sample(n=500, random_state=42)
    df_sample = pd.concat([safe_samples, malicious_samples]).sample(frac=1, random_state=42).reset_index(drop=True)
    
    print(f"Testing {len(df_sample)} URLs...")
    
    results = []
    last_botoi_call = 0
    
    for idx, row in df_sample.iterrows():
        url = row['url']
        true_label = row['true_label']
        
        # Make sure URL has a scheme, otherwise Botoi and URLScan return 400 Bad Request
        if not url.startswith("http://") and not url.startswith("https://"):
            url_to_test = "http://" + url
        else:
            url_to_test = url
            
        print(f"[{idx+1}/1000] Testing URL: {url_to_test}")
        
        sb_res, sb_time = check_safe_browsing(url_to_test)
        urlscan_res, urlscan_time = check_urlscan(url_to_test)
        
        # Enforce Botoi 10 requests / minute (6s gap)
        now = time.time()
        elapsed = now - last_botoi_call
        if elapsed < 6.1:
            time.sleep(6.1 - elapsed)
            
        botoi_res, botoi_time = check_botoi(url_to_test)
        last_botoi_call = time.time()
        
        results.append({
            "url": url,
            "true_label": true_label,
            "safe_browsing": sb_res,
            "safe_browsing_time": sb_time,
            "urlscan": urlscan_res,
            "urlscan_time": urlscan_time,
            "botoi": botoi_res,
            "botoi_time": botoi_time
        })
        
        pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
        print(f"  -> SB: {sb_res} ({sb_time:.1f}s) | URLScan: {urlscan_res} ({urlscan_time:.1f}s) | Botoi: {botoi_res} ({botoi_time:.1f}s)")
        
    print("Evaluation finished. Generating report...")
    df_results = pd.DataFrame(results)
    
    report_content = "=== URL Verifiers Evaluation Report ===\n\n"
    report_content += generate_report(df_results, "Google Safe Browsing", "safe_browsing", "safe_browsing_time")
    report_content += generate_report(df_results, "URLScan.io (Active Scan)", "urlscan", "urlscan_time")
    report_content += generate_report(df_results, "Botoi Phishing Check", "botoi", "botoi_time")
    
    with open(REPORT_TXT, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Report saved to {REPORT_TXT}")
    print(report_content)

if __name__ == "__main__":
    main()

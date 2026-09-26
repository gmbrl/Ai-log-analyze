# AI Log Analyzer

An AI-powered DevOps tool that reads system logs, 
detects errors and anomalies, and generates 
intelligent incident reports using LLM inference.

Built to simulate real-world Site Reliability 
Engineering (SRE) workflows.

---

## What It Does

- Reads system log files in real-time
- Detects ERROR, WARNING, and INFO patterns
- Sends logs to AI model for intelligent analysis
- Generates structured incident reports automatically

---

## Tech Stack

- Python 3
- Groq API (LLaMA 3.3 70B)
- Docker
- GitHub Actions (CI/CD)
- Linux/WSL

---

## How To Run

**Clone the repo:**
```bash
git clone https://github.com/gmbrl/ai-log-analyzer
cd ai-log-analyzer
```

**Add your Groq API key:**
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run the analyzer:**
```bash
python3 app.py
```

**Run with Docker:**
```bash
docker build -t ai-log-analyzer .
docker run ai-log-analyzer
```

---

## CI/CD Pipeline

Every push to master automatically triggers 
the GitHub Actions pipeline which installs 
dependencies and runs the analyzer.

---

## Author

Edwin Jonathan Chibuike  
DevOps & Cloud Engineering  
GitHub: edwinjonathanchibuike123-sys.

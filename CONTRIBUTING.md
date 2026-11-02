# Contributing to GhostBase 👻

Thank you for your interest in contributing to GhostBase! We welcome contributions, bug reports, and ideas from everyone.

---

## 🛠️ Development Setup

1. **Fork and Clone the repository:**
   ```bash
   git clone https://github.com/4yk5/GhostBase.git
   cd GhostBase
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run GhostBase locally:**
   ```bash
   python main.py
   ```

---

## 🧪 Running Tests

Before submitting a Pull Request, always make sure all test suites pass cleanly:

```bash
python tests/test_all.py
python tests/test_exhaustive.py
python tests/test_real_db.py
```

---

## 💡 How to Contribute

- **Report Bugs:** Open an issue using our [Bug Report Template](https://github.com/4yk5/GhostBase/issues/new?template=bug_report.yml).
- **Suggest Features:** Have an idea? Submit a [Feature Request](https://github.com/4yk5/GhostBase/issues/new?template=feature_request.yml).
- **Submit Pull Requests:**
  1. Fork the repo and create your branch from `main` (`git checkout -b feature/awesome-feature`).
  2. Keep code clean, readable, and follow the existing TUI architecture.
  3. Ensure all tests pass.
  4. Submit your Pull Request with a clear description of the changes!

---

## 📄 License

By contributing to GhostBase, you agree that your contributions will be licensed under the [MIT License](LICENSE).

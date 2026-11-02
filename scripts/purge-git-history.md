# Removing the 1 GB model files from git history

v1 committed `models/vosk-model-*` and `*.h5` files, plus 29 personal interview
reports. Deleting them in a new commit does **not** shrink the repo: they stay in
history. Rewrite history once:

```bash
pip install git-filter-repo
git filter-repo --invert-paths \
  --path models/ --path reports/ --path test.wav --path app.py --path utils/ --force
git remote add origin https://github.com/Abhenav-Jain/AI_Interview_Analyzer.git
git push --force origin main
```

Anyone with an old clone must re-clone. Do this *before* adding collaborators.

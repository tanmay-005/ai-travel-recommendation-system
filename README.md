# Travel Recommender Prototype

## Run demo
1. Install requirements:
   ```bash
   pip install pandas numpy scikit-learn flask flask-cors
   ```
2. Run offline demo:
   ```bash
   python recommender_demo.py
   ```
3. Run API:
   ```bash
   python app.py
   ```
   Test in browser:
   - http://127.0.0.1:5000/recommend_by_place?place=Red%20Fort
   - http://127.0.0.1:5000/recommend_for_user?user=U1
4. Frontend:
   ```bash
   python -m http.server 8000
   ```
   Then open http://localhost:8000/index.html

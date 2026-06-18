import sys
print("Python:", sys.executable)
try:
    from main import app
    print("App imported successfully")
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()

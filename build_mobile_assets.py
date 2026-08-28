import os
import shutil

def prepare_www():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    www_dir = os.path.join(base_dir, 'www')
    static_dir = os.path.join(base_dir, 'app', 'static')
    template_file = os.path.join(base_dir, 'app', 'templates', 'index.html')
    
    os.makedirs(www_dir, exist_ok=True)
    
    # 1. Copy static folder to www/static
    www_static = os.path.join(www_dir, 'static')
    shutil.copytree(static_dir, www_static, dirs_exist_ok=True)
    
    # 2. Copy index.html to www/index.html
    target_index = os.path.join(www_dir, 'index.html')
    shutil.copyfile(template_file, target_index)
    
    print(f"[OK] Successfully built standalone web assets in {www_dir}")

if __name__ == '__main__':
    prepare_www()

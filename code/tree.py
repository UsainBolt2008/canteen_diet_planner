import os
import argparse


def generate_tree(startpath, ignore_list=None):
    if ignore_list is None:
        ignore_list = []
    for root, dirs, files in os.walk(startpath):
        # 过滤忽略列表
        dirs[:] = [d for d in dirs if not any(ignore in d for ignore in ignore_list)]
        files = [f for f in files if not any(ignore in f for ignore in ignore_list)]

        level = root.replace(startpath, '').count(os.sep)
        if level == 0:
            print(root)
        else:
            indent = '│   ' * (level - 1) + '├── '
            print(f"{indent}{os.path.basename(root)}")
        subindent = '│   ' * level + '├── '
        for i, file in enumerate(files):
            if i == len(files) - 1 and not dirs:
                subindent = '│   ' * level + '└── '
            print(f"{subindent}{file}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Print tree of a directory.')
    parser.add_argument('path', nargs='?', default=r"C:\Users\asus\Desktop\程序算法实践\canteen_diet_planner", help='Path to the directory')
    args = parser.parse_args()

    ignore_patterns = ['__pycache__', '.pyc', '.git']
    generate_tree(args.path, ignore_patterns)
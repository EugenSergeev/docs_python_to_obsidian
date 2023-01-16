import re
from pathlib import Path
from loguru import logger

START_ROWS = "Здесь будут комментарии из файла\n\n\n\n\n\n\n\n\n\n---\n"

CURRENT_DIR = Path().cwd()
ENV_PATH_NAME = "venv"
DOCS_PATH_NAME = "Docs"


class Import:
    def __init__(self, abs_path: str):
        self.abs_path = abs_path
        self.name = self.abs_path.split('.')[-1]

    def __repr__(self):
        return f'<Import: {self.abs_path}>'

    def __str__(self):
        return self.__repr__()


class PyFile:
    def __init__(self, file_name: str | Path, project_path: str| Path):
        self.file = Path(file_name)
        self.project_path = Path(project_path)
        self.file_rows = self.get_rows_of_py_file()
        self.classes = self.get_classes()
        self.import_objects = self.get_imports()
        self.filename = self.file.as_posix()

    def get_rows_of_py_file(self):
        file = self.project_path / self.file
        with file.open(encoding='utf-8') as file:
            file_rows = file.readlines()
        return file_rows

    def get_imports(self):
        IMPORT_STRING = "import "
        FROM_STRING = "from "
        import_rows = []
        from_rows = []

        for row in self.file_rows:
            if row.strip().startswith(IMPORT_STRING):
                import_rows.append(row.strip()[len(IMPORT_STRING):])  # убираю слово import из строки
            elif row.strip().startswith(FROM_STRING):
                from_rows.append(row.strip()[len(FROM_STRING):])  # убираю слово from из строки

        import_objects = []
        for row in import_rows:
            import_names_str = row.split('as')[0].strip()
            import_names = [name.strip() for name in import_names_str.split(",")]
            import_objects += [Import(name) for name in import_names]
        for row in from_rows:
            import_parent = row.split(IMPORT_STRING)[0].strip()
            if import_parent.startswith("."):
                dot_count = len(re.findall(r'\.+', import_parent)[0])
                import_parent = self.get_parent_import(dot_count) + import_parent[dot_count:]
            import_elements = row.split(IMPORT_STRING)[1].split(",")
            for element in import_elements:
                import_name = f"{import_parent}." + element.split(" as ")[0].strip()
                import_objects.append(Import(import_name))
        return import_objects

    def get_parent_import(self, dot_count) -> str:
        parent = self.file
        for _ in range(dot_count):
            parent = parent.parent
        return ".".join(parent.parts) + "."

    def get_classes(self):
        class_definition_string = 'class '
        classes_rows = [row for row in self.file_rows if row.startswith(class_definition_string)]
        classes_names = []
        for row in classes_rows:
            row_ = row[len(class_definition_string):].strip()
            class_name = re.findall(r'\w*', row_)
            classes_names.append(class_name[0])
        return classes_names

    def get_module_name_for_import(self):
        return self.filename[:-3].replace("/", ".")

    def __repr__(self):
        return str(self.file.absolute()).replace(str(Path().cwd().absolute()), "")

    def __str__(self):
        return self.__repr__()


def get_all_py_files_without_env(env_path, path_project):
    all_py_files = [file for file in path_project.glob("**/*.py")
                    if not str(file.absolute()).startswith(str(env_path.absolute()))]
    py_files = []
    for file in all_py_files:
        file_name_without_path_project = str(file.absolute().as_posix()).replace(
            str(path_project.absolute().as_posix()) + "/", "")
        file_ = Path(file_name_without_path_project)
        py_files.append(file_)
    return py_files

@logger.catch()
def start_generate(project_path=CURRENT_DIR, env_path_name=ENV_PATH_NAME, docs_path=None):
    project_path = Path(project_path)
    docs_path = Path(docs_path) if docs_path else Path().cwd() / DOCS_PATH_NAME / project_path.name
    env_path = Path(project_path) / Path(env_path_name)
    py_files = get_all_py_files_without_env(env_path, project_path)
    py_file_objects = [PyFile(file_path, project_path) for file_path in py_files]

    files_text_dict = {}  # тут хранятся строки для всех файлов MD
    for py_file in py_files:
        rows = [START_ROWS, f'[Link to file]({py_file.absolute().as_uri()})']
        files_text_dict[py_file.as_posix()] = rows

    all_classes_links = {py_obj.get_module_name_for_import() + "." + class_: f"{py_obj.filename}#{class_}"
                         for py_obj in py_file_objects
                         for class_ in py_obj.classes}

    py_file_import_classes_dict = {}
    for py_obj in py_file_objects:
        if py_obj.classes:
            files_text_dict[py_obj.filename].append(f'# Implemented classes')
            for class_ in py_obj.classes:
                files_text_dict[py_obj.filename].append(f'#### {class_}')

        modules = []
        for import_ in py_obj.import_objects:
            module_name_path = Path(import_.abs_path.replace(".", "/"))

            for i in range(len(module_name_path.parts), 0, -1):
                name = "/".join(module_name_path.parts[:i])
                name_with_py = Path(str(name) + ".py")
                if name_with_py in py_files:
                    row = f"[[{name_with_py.as_posix()}|{name_with_py.name}]]"
                    modules.append(row)
                    break
                elif i == len(module_name_path.parts):
                    py_file_import_classes_dict.setdefault(py_obj.filename, [])
                    py_file_import_classes_dict[py_obj.filename].append(import_.abs_path)

        if modules:
            files_text_dict[py_obj.filename].append(f'# Imported modules')
            files_text_dict[py_obj.filename] += list(set(modules))

    for py_file_name, classes in py_file_import_classes_dict.items():
        user_classes = []
        unknown_imports = []
        for class_ in classes:
            if class_ in all_classes_links:
                user_classes.append(all_classes_links[class_])
            else:
                unknown_imports.append(class_)

        if user_classes:
            files_text_dict[py_file_name].append("# Imported classes")
            for class_ in user_classes:
                files_text_dict[py_file_name].append(f"[[{class_}|{class_.split('#')[1]}]]")
        if unknown_imports:
            files_text_dict[py_file_name].append("# Other imports")
            for import_ in unknown_imports:
                files_text_dict[py_file_name].append(import_)

    for py_file_name, rows in files_text_dict.items():
        doc_file = docs_path / (py_file_name + ".md")
        doc_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with doc_file.open(mode="w", encoding='utf-8') as doc_file_obj:
                doc_file_obj.write("\n".join(rows))
        except:
            pass


if __name__ == '__main__':
    start_generate(r"d:\dev\RFM")

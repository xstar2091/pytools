import pathlib
import sys
import subprocess
import rich.console
import rich.table


class CommandLine(object):
    # 搜索目录
    dir = pathlib.Path(__file__).parent
    # 搜索层级
    search_level = 2


def print_help():
    print(f'''根据指定目录和指定搜索深度，查找纳入版本管理系统的项目，并列出项目状态

{sys.argv[0]}
    搜索当前目录，搜索深度为2

{sys.argv[0]} search_path
    搜索search_path目录，搜索深度为2

{sys.argv[0]} search_path search_level
    搜索search_path目录，搜索深度为search_level''')
    pass


def print_version():
    print("v 1.0.0")


def init_command_line():
    if len(sys.argv) == 2:
        if sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print_help()
            return False
        elif sys.argv[1] == "--version" or sys.argv[1] == "-v":
            print_version()
            return False
        else:
            CommandLine.dir = pathlib.Path(sys.argv[1])
    elif len(sys.argv) == 3:
        CommandLine.dir = pathlib.Path(sys.argv[1])
        try:
            CommandLine.search_level = int(sys.argv[2])
        except ValueError:
            print_help()
            return False
    path = pathlib.Path(CommandLine.dir)
    if not path.is_dir() and not path.is_file():
        print_help()
        return False
    if path.is_file():
        path = path.parent
    CommandLine.dir = path.resolve()
    return True


class ProjectInfo(object):
    def __init__(self):
        # 项目名称
        self.project = ""
        # 版本库类型，git或svn
        self.cvs_type = ""
        # 分支名称
        self.branch_name = ""
        # 可能的值包含
        # done：所有修改都已提交并push到服务器
        # modified：已修改未commit
        # committed：已commit未push
        self.status = ""
        # 更改的文件的数量
        self.modified_count = 0
        # 未纳入版本管理的文件数量
        self.untracked_count = 0
        # 删除的文件的数量
        self.deleted_count = 0
        # 新文件的数量
        self.new_count = 0


class PathInfo(object):
    def __init__(self, path, cvs_type):
        self.path = path
        self.cvs_type = cvs_type


class Branch(object):
    def process(self, path: str) -> ProjectInfo:
        pass

    @staticmethod
    def run_command(cmd: str, path: str):
        p = subprocess.Popen(cmd, cwd=path, stdout=subprocess.PIPE)
        return p.stdout.readlines()
        pass


class GitBranch(Branch):
    def process(self, path: str) -> ProjectInfo:
        project_info = ProjectInfo()
        project_info.project = pathlib.Path(path).name
        project_info.cvs_type = "git"
        out_list = self.run_command("git status", path)
        untracked_files_start = False
        for out in out_list:
            line = out.decode("utf8").strip("*").strip("\n").strip("\r")
            if line == "":
                continue
            if line[0].isspace():
                line = line.strip()
                if line.startswith("("):
                    if line.find("git push") > 0 and line.find("publish your local commits") > 0:
                        project_info.status = "committed"
                    continue
                if untracked_files_start:
                    project_info.untracked_count += 1
                elif line.startswith("modified:"):
                    project_info.modified_count += 1
                elif line.startswith("deleted:"):
                    project_info.deleted_count += 1
                elif line.startswith("new file:"):
                    project_info.new_count += 1
            else:
                untracked_files_start = False
                if line.startswith("("):
                    continue
                elif line.startswith("On branch"):
                    project_info.branch_name = line.split()[-1]
                elif line.startswith("nothing to commit"):
                    if project_info.status == "":
                        project_info.status = "done"
                elif line.startswith("Untracked files:"):
                    untracked_files_start = True
        if project_info.status != "committed" and project_info.status != "done":
            project_info.status = "modified"
        return project_info
        pass


class BranchManager(object):
    def __init__(self):
        self.supported_cvs_type = {
            ".git": "git",
            ".svn": "svn"
        }
        self.create_branch_helper = {
            "git": lambda: GitBranch()
        }
        self.modified_color = "red"
        self.current_level = 0
        pass

    def work(self):
        path_list = self.__collect_path()
        project_info_list = []
        for item in path_list:
            if item.cvs_type not in self.create_branch_helper:
                continue
            branch = self.create_branch_helper[item.cvs_type]()
            project_info = branch.process(item.path)
            project_info_list.append(project_info)
        self.__print_project_info(project_info_list)
        pass

    def __collect_path(self):
        path_list = []
        self.current_level = 1
        self.__do_collect_path(pathlib.Path(CommandLine.dir), path_list)
        return path_list
        pass

    def __do_collect_path(self, path: pathlib.Path, path_list: list):
        if self.current_level > CommandLine.search_level:
            return
        for p in path.glob("*"):
            if p.is_file():
                continue
            if p.name in self.supported_cvs_type.keys():
                cvs_type = self.supported_cvs_type[p.name]
                path_list.append(PathInfo(path, cvs_type))
            else:
                self.current_level += 1
                self.__do_collect_path(path.joinpath(p), path_list)
                self.current_level -= 1
        pass

    def __print_project_info(self, project_info_list):
        console = rich.console.Console()
        console.print("branch info")
        table = rich.table.Table(show_header=True, header_style="bold magenta")
        table.add_column("project")
        table.add_column("branch")
        table.add_column("status")
        for project_info in project_info_list:
            if project_info.status == "done":
                table.add_row(project_info.project, project_info.branch_name, project_info.status)
            else:
                table.add_row(f"[{self.modified_color}]{project_info.project}[/{self.modified_color}]",
                              f"[{self.modified_color}]{project_info.branch_name}[/{self.modified_color}]",
                              f"[{self.modified_color}]{project_info.status}[/{self.modified_color}]")
        console.print(table)

        console.print("modified info")
        table = rich.table.Table(show_header=True, header_style="bold magenta")
        table.add_column("project")
        table.add_column("modified")
        table.add_column("untracked")
        table.add_column("deleted")
        table.add_column("new")
        for project_info in project_info_list:
            table.add_row(project_info.project,
                          str(project_info.modified_count), str(project_info.untracked_count),
                          str(project_info.deleted_count), str(project_info.new_count))
        console.print(table)
        pass


def main():
    if not init_command_line():
        return
    mgr = BranchManager()
    mgr.work()


if __name__ == '__main__':
    main()

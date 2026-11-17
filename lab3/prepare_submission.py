"""Stage the requested submission layout and package a supplied report."""

import argparse
import pathlib
import shutil
import zipfile

_NAME = "实验3_241220158_王能"
_CODE_FILES = (".gitignore", "README.md", "pyproject.toml", "启动校园拾光.cmd")


def collect(root):
    """Yield only UML, source modules, and reproducible verification code."""
    for file in sorted((root / "UML").iterdir()):
        if file.suffix in {".png", ".puml"}:
            yield file
    code = root / "code"
    for name in _CODE_FILES:
        yield code / name
    for folder, extensions in (
        ("campus", {".py", ".sql"}),
        ("campus/mobile_ui", {".html", ".css", ".js"}),
        ("campus/mobile_ui/assets", {".jpg", ".ttf", ".txt", ".md"}),
        ("tests", {".py"}),
        ("tools", {".py"}),
    ):
        for file in sorted((code / folder).iterdir()):
            if file.suffix in extensions and file.is_file():
                yield file
    for file in sorted((code / "android").rglob("*")):
        if file.is_file() and file.suffix in {".java", ".xml", ".ps1"}:
            yield file


def prepare(root, output, report):
    """Stage selected files and optionally write a verified archive."""
    sources = list(collect(root))
    paths = {path.relative_to(root) for path in sources}
    folder = output / _NAME
    archive = output / f"{_NAME}.zip"
    if report:
        with report.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ValueError("请提供有效的实验报告 PDF")
    for source in sources:
        target = folder / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if not report:
        return folder
    report_name = pathlib.Path("实验报告.pdf")
    target_report = folder / report_name
    if report.resolve() != target_report.resolve():
        shutil.copy2(report, target_report)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output_zip:
        for relative in sorted(paths | {report_name}):
            output_zip.write(folder / relative, pathlib.Path(_NAME) / relative)
    with zipfile.ZipFile(archive) as output_zip:
        if output_zip.testzip() is not None:
            raise OSError("提交包完整性检查失败")
    return archive


def main():
    """Prepare files outside the Git worktree by default."""
    root = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path,
                        default=root.parents[1] / "实验三_提交准备")
    parser.add_argument("--report", type=pathlib.Path)
    options = parser.parse_args()
    artifact = prepare(root, options.output.resolve(), options.report)
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

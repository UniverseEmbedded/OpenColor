- 不要直接去用`python`或`.pixi\envs\default\python.exe`命令，建议使用`pixi run python`
- 不要胡乱调用`pixi run test -q`，项目暂时并没有任何测试用例
- 写代码（尤其是python脚本）的时候，不要pass任何一个可能出现的异常，禁止写出以下这种代码：

```
try:
    # xxx
except Exception:
    pass
```

- 不要暗搓搓的把异常（例如函数报错，缺少依赖库，一些和系统有关用户提示等）只展示在UI上，而是必须同时打印到控制台，便于调试，你要记住不是控制台越干净越好
- 注释，UI文本，打印文本全用中文
- 不要随意使用`sys.path.append(os.path.dirname(__file__))`，等path操作语句，除非没办法
- **日志使用规范**：项目使用 `loguru` 作为日志库，禁止直接使用 `print()` 输出日志信息
  - 正确做法：`from oc_core_02.utils.logger import get_logger; logger = get_logger(__name__); logger.info("消息")`
  - 错误做法：`print("消息")`
  - 异常处理时直接使用 `logger.error("错误: {}", e)` 并抛出异常，不要使用 `traceback.print_exc()`
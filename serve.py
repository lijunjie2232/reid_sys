"""启动 Smart Gateway：uvicorn reid_sys.api:app

    uv run python serve.py            # http://127.0.0.1:8000

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("reid_sys.api:app", host="127.0.0.1", port=8000, reload=False)

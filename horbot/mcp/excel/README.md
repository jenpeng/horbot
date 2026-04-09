# Excel MCP Server

Excel 文件操作 MCP Server，支持创建、读取、写入 Excel 文件。

## 安装依赖

```bash
pip install openpyxl
```

## 配置

在 `config.json` 中添加：

```json
{
  "tools": {
    "mcpServers": {
      "excel": {
        "command": "python",
        "args": ["-m", "horbot.mcp.excel.server"],
        "tool_timeout": 60
      }
    }
  }
}
```

## 可用工具

### excel_create_workbook
创建新的 Excel 工作簿。

**参数：**
- `filepath` (必需): 文件保存路径
- `sheet_name` (可选): 工作表名称，默认 "Sheet"

**示例：**
```json
{
  "filepath": "/path/to/data.xlsx",
  "sheet_name": "数据表"
}
```

### excel_write_data
向 Excel 文件写入数据。

**参数：**
- `filepath` (必需): Excel 文件路径
- `data` (必需): 二维数组数据
- `start_cell` (可选): 起始单元格，默认 "A1"
- `sheet_name` (可选): 工作表名称

**示例：**
```json
{
  "filepath": "/path/to/data.xlsx",
  "data": [
    ["姓名", "年龄", "城市"],
    ["张三", 25, "北京"],
    ["李四", 30, "上海"]
  ],
  "start_cell": "A1"
}
```

### excel_read_data
读取 Excel 数据。

**参数：**
- `filepath` (必需): Excel 文件路径
- `range` (可选): 读取范围，如 "A1:C10"
- `sheet_name` (可选): 工作表名称

### excel_set_style
设置单元格样式。

**参数：**
- `filepath` (必需): Excel 文件路径
- `range` (必需): 样式范围
- `bold` (可选): 是否加粗
- `font_size` (可选): 字体大小
- `bg_color` (可选): 背景颜色（十六进制）
- `align` (可选): 对齐方式 (left/center/right)
- `sheet_name` (可选): 工作表名称

### excel_list_sheets
列出所有工作表。

### excel_add_sheet
添加新工作表。

## 使用示例

```python
# AI 可以通过 MCP 工具调用：

# 1. 创建工作簿
excel_create_workbook(filepath="/tmp/demo.xlsx", sheet_name="项目进度")

# 2. 写入数据
excel_write_data(
    filepath="/tmp/demo.xlsx",
    data=[
        ["项目名称", "负责人", "状态", "进度"],
        ["网站重构", "张三", "进行中", "60%"],
        ["APP开发", "李四", "已完成", "100%"]
    ]
)

# 3. 设置标题样式
excel_set_style(
    filepath="/tmp/demo.xlsx",
    range="A1:D1",
    bold=True,
    bg_color="4472C4",
    align="center"
)

# 4. 读取数据
excel_read_data(filepath="/tmp/demo.xlsx")
```

## 注意事项

- 仅支持 `.xlsx` 格式（Excel 2007+）
- 文件路径需要绝对路径
- 写入操作会覆盖原有内容
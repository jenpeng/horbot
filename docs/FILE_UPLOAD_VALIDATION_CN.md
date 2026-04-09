# 文件上传验证规范文档

## 1. 概述

本文档定义了文件上传验证的规范规则，包括文件格式、文件大小和文件类型的验证标准。本规范适用于所有文件上传场景，确保系统安全性和数据完整性。

## 2. 验证规则

### 2.1 支持的文件格式

系统支持以下文件格式的上传：

| 类别 | 格式 | 扩展名 | MIME类型 |
|------|------|--------|----------|
| 文档 | Word文档 | .doc, .docx | application/msword, application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| 文档 | PDF | .pdf | application/pdf |
| 文档 | 文本文件 | .txt | text/plain |
| 文档 | Markdown | .md, .markdown | text/markdown |
| 电子表格 | Excel | .xls, .xlsx | application/vnd.ms-excel, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| 演示文稿 | PowerPoint | .ppt, .pptx | application/vnd.ms-powerpoint, application/vnd.openxmlformats-officedocument.presentationml.presentation |
| 图像 | JPEG | .jpg, .jpeg | image/jpeg |
| 图像 | PNG | .png | image/png |
| 图像 | GIF | .gif | image/gif |
| 图像 | WebP | .webp | image/webp |
| 图像 | SVG | .svg | image/svg+xml |
| 音频 | MP3 | .mp3 | audio/mpeg |
| 音频 | WAV | .wav | audio/wav |
| 音频 | OGG | .ogg | audio/ogg |
| 视频 | MP4 | .mp4 | video/mp4 |
| 视频 | WebM | .webm | video/webm |
| 视频 | AVI | .avi | video/x-msvideo |
| 压缩包 | ZIP | .zip | application/zip |
| 压缩包 | TAR | .tar | application/x-tar |
| 压缩包 | GZIP | .gz | application/gzip |
| 压缩包 | 7z | .7z | application/x-7z-compressed |
| 代码 | JavaScript | .js | application/javascript |
| 代码 | Python | .py | text/x-python |
| 代码 | JSON | .json | application/json |
| 代码 | XML | .xml | application/xml |
| 代码 | HTML | .html, .htm | text/html |
| 代码 | CSS | .css | text/css |

### 2.2 文件大小限制

| 文件类型 | 最大大小 | 说明 |
|----------|----------|------|
| 普通文件 | 50MB | 适用于大多数文档、图片、音频文件 |
| 视频文件 | 500MB | 适用于视频文件 |
| 压缩包 | 100MB | 适用于压缩文件 |
| 图像文件 | 20MB | 专门针对图像文件 |
| 文档文件 | 30MB | 专门针对Word、PDF等文档 |

**默认限制**：如果文件类型未明确指定，默认最大上传大小为 **50MB**。

### 2.3 文件类型验证规则

#### 2.3.1 MIME类型验证
- 必须基于文件内容（Magic Bytes）进行验证，而非仅依赖文件扩展名
- 必须验证HTTP请求中的Content-Type头与实际文件MIME类型一致

#### 2.3.2 扩展名验证
- 文件扩展名必须与支持的格式列表匹配
- 扩展名不区分大小写
- 禁止使用双扩展名绕过验证（如file.txt.exe）

#### 2.3.3 危险文件类型禁止上传

以下文件类型被严格禁止上传：

| 危险类型 | 原因 |
|----------|------|
| .exe | 可执行文件，可能包含恶意代码 |
| .bat, .cmd, .sh | 脚本文件，可能执行系统命令 |
| .msi | Windows安装程序 |
| .scr | 屏幕保护程序 |
| .vbs, .ps1 | 脚本文件 |
| .jar | Java可执行文件 |
| .app | macOS应用程序 |
| .dmg | macOS磁盘映像 |
| .deb, .rpm | Linux软件包 |
| .html, .htm | 可能包含恶意脚本（仅在特定场景允许） |

## 3. 验证流程

### 3.1 验证步骤

```
┌─────────────────────────────────────────────────────────────┐
│                      文件上传验证流程                         │
├─────────────────────────────────────────────────────────────┤
│  1. 检查文件是否存在                                         │
│       ↓                                                      │
│  2. 检查文件大小是否超过限制                                  │
│       ↓                                                      │
│  3. 检查文件扩展名是否合法                                     │
│       ↓                                                      │
│  4. 验证文件MIME类型（Magic Bytes）                          │
│       ↓                                                      │
│  5. 验证Content-Type头与实际类型是否一致                      │
│       ↓                                                      │
│  6. 扫描文件是否包含恶意内容（可选）                           │
│       ↓                                                      │
│  7. 返回验证结果                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 验证优先级

1. **第一步**：检查文件是否为空或不存在
2. **第二步**：检查文件大小
3. **第三步**：检查扩展名
4. **第四步**：验证MIME类型（内容验证）
5. **第五步**：一致性检查

## 4. 错误处理

### 4.1 错误码定义

| 错误码 | 错误类型 | 说明 |
|--------|----------|------|
| E001 | FILE_EMPTY | 文件为空 |
| E002 | FILE_TOO_LARGE | 文件大小超过限制 |
| E003 | INVALID_EXTENSION | 文件扩展名不合法 |
| E004 | INVALID_MIME_TYPE | 文件MIME类型不匹配 |
| E005 | FORBIDDEN_FILE_TYPE | 禁止上传的文件类型 |
| E006 | CORRUPTED_FILE | 文件已损坏 |
| E007 | FILE_NAME_TOO_LONG | 文件名过长 |
| E008 | INVALID_CHARACTERS | 文件名包含非法字符 |

### 4.2 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "E002",
    "message": "文件大小超过限制",
    "details": {
      "maxSize": "50MB",
      "actualSize": "75MB"
    }
  }
}
```

## 5. 配置说明

### 5.1 配置文件结构

```yaml
upload:
  validation:
    # 是否启用验证
    enabled: true
    
    # 默认最大文件大小（字节）
    max_file_size: 52428800
    
    # 按文件类型设置大小限制
    size_limits:
      video: 524288000      # 500MB
      archive: 104857600    # 100MB
      image: 20971520       # 20MB
      document: 31457280    # 30MB
    
    # 允许的文件扩展名
    allowed_extensions:
      - doc, docx, pdf, txt, md
      - xls, xlsx, ppt, pptx
      - jpg, jpeg, png, gif, webp, svg
      - mp3, wav, ogg
      - mp4, webm, avi
      - zip, tar, gz, 7z
      - js, py, json, xml, html, css
    
    # 禁止的文件扩展名
    forbidden_extensions:
      - exe, bat, cmd, sh, msi
      - scr, vbs, ps1, jar
      - app, dmg, deb, rpm
    
    # 是否启用MIME类型内容验证
    validate_mime_type: true
    
    # 是否检查Content-Type一致性
    check_content_type_header: true
```

## 6. 安全建议

### 6.1 额外安全措施

1. **文件重命名**：上传后自动重命名文件，使用随机生成的唯一ID
2. **存储隔离**：将用户上传的文件存储在独立的存储区域，与系统文件隔离
3. **病毒扫描**：对上传的可执行文件进行病毒扫描
4. **访问控制**：限制上传文件的访问权限
5. **日志记录**：记录所有文件上传操作，便于审计

### 6.2 性能优化

1. **流式处理**：大文件使用流式处理，避免内存溢出
2. **分片上传**：支持大文件分片上传
3. **缓存验证结果**：缓存已验证的文件信息

## 7. 附录

### 7.1 常用文件Magic Bytes

| 文件类型 | Magic Bytes (十六进制) |
|----------|------------------------|
| JPEG | FF D8 FF |
| PNG | 89 50 4E 47 0D 0A 1A 0A |
| GIF | 47 49 46 38 |
| PDF | 25 50 44 46 |
| ZIP | 50 4B 03 04 |
| MP3 | 49 44 33 或 FF FB |
| MP4 | 00 00 00 18 66 74 79 70 |

### 7.2 更新历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| 1.0.0 | 2024-01-01 | 初始版本 |

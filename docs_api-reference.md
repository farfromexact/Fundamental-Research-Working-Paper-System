# Hyby.DataApi API 接口文档

本文用于指导前端与客户侧调用方正确调用 Hyby.DataApi 业务接口。文档内容基于当前控制器、参数包与 DAL 返回字段整理，优先覆盖常用请求参数、鉴权方式、返回结构和调用示例。

## 接口目录

### 研报类

- [研报列表查询 `GET/POST /api/RReport`](#研报列表查询-getpost-apirreport)
- [研报详情查询 `GET /api/RReport/{id}`](#研报详情查询-get-apirreportid)

### 信披类

- [股票公告查询 `GET/POST /api/Disclosure/stock`](#股票公告查询-getpost-apidisclosurestock)
- [预披露公告查询 `GET/POST /api/Disclosure/pre`](#预披露公告查询-getpost-apidisclosurepre)
- [IR 互动问答查询 `GET/POST /api/Disclosure/irqna`](#ir-互动问答查询-getpost-apidisclosureirqna)
- [调研记录查询 `GET/POST /api/Disclosure/iractivity`](#调研记录查询-getpost-apidisclosureiractivity)
- [公司声音查询 `GET/POST /api/Disclosure/voice`](#公司声音查询-getpost-apidisclosurevoice)

### 新闻类

- [股票新闻查询 `GET/POST /api/News/stock`](#股票新闻查询-getpost-apinewsstock)
- [股票新闻详情 `GET /api/News/stock/{id}`](#股票新闻详情-get-apinewsstockid)
- [期货新闻查询 `GET/POST /api/News/future`](#期货新闻查询-getpost-apinewsfuture)
- [期货新闻详情 `GET /api/News/future/{id}`](#期货新闻详情-get-apinewsfutureid)
- [政府工作新闻查询 `GET/POST /api/News/gov`](#政府工作新闻查询-getpost-apinewsgov)
- [政府工作新闻详情 `GET /api/News/gov/{id}`](#政府工作新闻详情-get-apinewsgovid)
- [行业新闻查询 `GET/POST /api/News/industry`](#行业新闻查询-getpost-apinewsindustry)
- [行业新闻详情 `GET /api/News/industry/{id}`](#行业新闻详情-get-apinewsindustryid)
- [宏观新闻查询 `GET/POST /api/News/macro`](#宏观新闻查询-getpost-apinewsmacro)
- [宏观新闻详情 `GET /api/News/macro/{id}`](#宏观新闻详情-get-apinewsmacroid)
- [负面新闻查询 `GET/POST /api/News/neg`](#负面新闻查询-getpost-apinewsneg)
- [负面新闻详情 `GET /api/News/neg/{id}`](#负面新闻详情-get-apinewsnegid)

### 综合资讯类

- [申万精品摘要内容查询 `GET/POST /api/PremiumInfo/brief`](#申万精品摘要内容查询-getpost-apipremiuminfobrief)
- [申万精品资讯列表查询 `GET/POST /api/PremiumInfo/list`](#申万精品资讯列表查询-getpost-apipremiuminfolist)
- [混合资讯列表查询 `GET/POST /api/CompInfo/list`](#混合资讯列表查询-getpost-apicompInfolist)

### 文件下载

- [文件下载 `GET/POST /api/Download`](#文件下载-getpost-apidownload)

## 通用约定

### Base URL

- 本地或部署环境通常为 `http://{host}:{port}` 或反向代理后的 HTTPS 地址
- 文档中的路径均为相对路径，调用时请拼接实际服务地址
- ASP.NET Core 路由大小写不敏感，示例使用控制器当前命名形式

### 业务接口鉴权

业务数据接口需要 API Key，并按以下优先级读取：

1. 查询参数或表单参数 `apikey`
2. 请求头 `Authorization: Bearer <api-key>`
3. 请求头 `Hydata-Apikey: <api-key>`

注意：`POST application/json` 请求体中的 `apikey` 不参与反序列化，JSON 请求推荐使用 `Authorization: Bearer <api-key>` 或 `Hydata-Apikey` 请求头。

### 请求绑定方式

- `GET`：通过 query string 传参，例如 `?psize=20&pno=1`
- `POST application/json`：通过 JSON body 传参，属性名大小写不敏感
- `POST application/x-www-form-urlencoded`：通过表单字段传参
- 列表查询接口必须传 `psize`，且 `psize` 不能超过 `200`
- `pno` 从 `1` 开始；未传时由底层分页逻辑按第一页处理
- 多值参数通常支持英文逗号 `,` 或分号 `;` 分隔
- 日期参数建议使用 `yyyy-MM-dd`，也可使用可被 .NET 解析的日期时间字符串

### 通用分页返回

业务列表接口统一返回 `PagedRowsResult`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `reccount` | `number \| null` | 符合条件的总记录数 |
| `psize` | `number \| null` | 每页记录数 |
| `pno` | `number \| null` | 当前页号 |
| `rows` | `object[] \| null` | 当前页数据行 |

业务详情接口统一返回 `ObjectDataResult`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `data` | `object \| null` | 详情数据对象 |

### 通用错误返回

业务接口错误统一返回 `ErrorResult`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | `number` | HTTP 状态码枚举值 |
| `code` | `number` | 业务错误码 |
| `message` | `string \| null` | 错误描述 |

常见错误码：

| code | HTTP | 说明 |
| --- | --- | --- |
| `100` | `500` | 服务端内部错误 |
| `102` | `400` | 请求参数格式错误 |
| `103` | `400` | 请求参数错误 |
| `104` | `401` | API Key 验证失败 |
| `108` | `403` | 用户 IP 地址访问受限 |
| `110` | `404` | 对象未找到 |
| `111` | `403` | 数据权限无效 |
| `112` | `403` | 文件下载功能受限 |
| `113` | `403` | 数据查询功能受限 |
| `114` | `500` | CRM 返回错误 |

示例：

```json
{
  "status": 401,
  "code": 104,
  "message": "请求未提交APIKEY"
}
```

### 资讯类别 infotype

文件下载接口使用 `infotype` 标识资讯类别，当前下载逻辑明确支持：

| infotype | 名称 | 所属模块 |
| --- | --- | --- |
| `1` | 研究报告 | 研报 |
| `7` | 股票公告 | 信披 |
| `9` | 预披露公告 | 信披 |
| `11` | 调研记录 | 信披 |

枚举中还定义了 `3` 行业资讯、`4` 政府工作、`5` 宏观新闻、`6` 公司新闻、`10` IR 互动问答、`16` 负面新闻、`17` 公司声音、`19` 期货新闻等类型，但文件下载当前主要处理上表四类附件。

## 研报列表查询 `GET/POST /api/RReport`

**接口描述**

按日期、标题关键词、证券代码、研报分类、行业、机构、作者、评级等条件分页查询研究报告。

**请求路径**

`/api/RReport`

**请求方法**

`GET`、`POST`

**HTTP 鉴权标头**

`Authorization: Bearer <api-key>` 或 `Hydata-Apikey: <api-key>`；也可在 query/form 中传 `apikey`。

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |
| `startdate` | query/body/form | `string` | 否 | 报告日期下界；未传时默认按 `enddate` 或当天向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 报告日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号，从 `1` 开始 |
| `brief` | query/body/form | `number` | 否 | `1` 返回列表摘要 `BriefText`；默认返回空摘要 |
| `wx` | query/body/form | `boolean` | 否 | 是否显示微信公众号研报，默认 `true` |
| `title` | query/body/form | `string` | 否 | 标题关键词。多个关键词用 `,` 或 `;` 分隔；`&&` 表示子关键词且关系；前缀 `!` 表示排除 |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `kind` | query/body/form | `string` | 否 | 研报类别 ID，可传一级或二级分类，多个用 `,` 或 `;` 分隔 |
| `swind_ids` | query/body/form | `string` | 否 | 申万行业 ID，多个用 `,` 或 `;` 分隔 |
| `star` | query/body/form | `number` | 否 | `1` 仅查明星分析师 |
| `inst_name` | query/body/form | `string` | 否 | 机构名称，多个用 `,` 或 `;` 分隔 |
| `author_name` | query/body/form | `string` | 否 | 作者名称，多个用 `,` 或 `;` 分隔 |
| `qmxhy_name` | query/body/form | `string` | 否 | 启明星行业名称，多个用 `,` 或 `;` 分隔 |
| `logor` | query/body/form | `boolean` | 否 | 多条件逻辑关系；`false` 为与，`true` 为或，默认 `false` |
| `inst_ids` | query/body/form | `string` | 否 | 机构 ID，多个用 `,` 或 `;` 分隔 |
| `gchange` | query/body/form | `string` | 否 | 评级调整，多个用 `,` 或 `;` 分隔 |
| `gscore` | query/body/form | `string` | 否 | 评级评分，多个用 `,` 或 `;` 分隔 |
| `lang` | query/body/form | `number` | 否 | 语言：`1` 英文，`0` 中文 |
| `market` | query/body/form | `string` | 否 | 市场代码，如 `HK`、`CN`、`World`，多个用 `,` 或 `;` 分隔 |
| `docfmt` | query/body/form | `string` | 否 | 文档格式，如 `EXCEL`、`PPT`，多个用 `,` 或 `;` 分隔 |
| `minpage` | query/body/form | `number` | 否 | 最小报告页数 |
| `maxpage` | query/body/form | `number` | 否 | 最大报告页数 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 常用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ReportID` | `number` | 研报 ID，可用于详情与下载 |
| `ReportDate` | `string` | 报告日期，格式 `yyyy-MM-dd` |
| `CreateTime` | `string` | 创建时间 |
| `InstituteID` | `number` | 机构 ID |
| `InstituteNameCN` | `string` | 机构中文名 |
| `AuthorName` | `string` | 作者名 |
| `IsAuthorStar` | `number` | 是否明星分析师标记 |
| `KindID` / `KindName` | `number/string` | 一级研报分类 |
| `Kind2ID` / `Kind2Name` | `number/string` | 二级研报分类 |
| `IndustryName` | `string` | 行业名称 |
| `StkCode` | `string` | 证券代码 |
| `StkName` | `string` | 证券简称 |
| `Page` | `number` | 页数 |
| `Size` | `number` | 文件大小 |
| `Title` | `string` | 标题 |
| `HaveBrief` | `number` | 是否有摘要 |
| `GradeName` | `string` | 评级名称 |
| `Score` | `number` | 评级分数 |
| `GradeChange` | `string` | 评级调整 |
| `filemode` | `number` | 文件模式 |
| `IsEnglish` | `number` | 是否英文研报 |
| `ExchangeType` | `string` | 市场/交易所类型 |
| `BriefText` | `string` | `brief=1` 时返回截断后的摘要 |

<details>
<summary>调用示例</summary>

```http
GET /api/RReport?startdate=2026-01-01&enddate=2026-05-14&stock=600000&brief=1&psize=20&pno=1 HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```json
{
  "reccount": 128,
  "psize": 20,
  "pno": 1,
  "rows": [
    {
      "ReportID": 123456,
      "ReportDate": "2026-05-14",
      "InstituteNameCN": "示例证券",
      "AuthorName": "张三",
      "StkCode": "600000",
      "StkName": "浦发银行",
      "Title": "银行行业研究报告",
      "BriefText": "报告摘要..."
    }
  ]
}
```

</details>

## 研报详情查询 `GET /api/RReport/{id}`

**接口描述**

按研报 ID 查询单篇研报详情。

**请求路径**

`/api/RReport/{id}`

**请求方法**

`GET`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | `number` | 是 | 研报 ID |
| `brief` | query | `number` | 否 | `1` 返回完整摘要 `Brief` |
| `apikey` | query | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `ObjectDataResult`。`data` 常用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ReportID` | `number` | 研报 ID |
| `Title` | `string` | 标题 |
| `ReportDate` | `string` | 报告日期 |
| `InstituteID` / `InstituteNameCN` | `number/string` | 机构信息 |
| `AuthorID` / `AuthorName` | `number/string` | 作者信息 |
| `KindID` / `KindName` | `number/string` | 一级分类 |
| `Kind2ID` / `Kind2Name` | `number/string` | 二级分类 |
| `IndustryID` / `IndustryName` | `number/string` | 行业信息 |
| `StkCode` / `SName` | `string/string` | 证券代码与名称 |
| `GradeName` / `GradeChange` / `Score` | `string/string/number` | 评级信息 |
| `Page` / `Size` | `number/number` | 页数与文件大小 |
| `FileModeID` | `number` | 文件模式 |
| `WXURL` | `string \| null` | 微信研报原文地址 |
| `WXPic` | `number \| null` | 是否存在微信原文缩略图 |
| `CNTrans` | `number \| null` | 是否存在中文译文 |
| `CNENTrans` | `number \| null` | 是否存在中英对照译文 |
| `aichat` | `number \| null` | 是否存在 AI 解读数据 |
| `Brief` | `string \| null` | `brief=1` 时返回完整摘要 |

## 股票公告查询 `GET/POST /api/Disclosure/stock`

**接口描述**

按日期、证券代码、公告类型、标题关键词等条件分页查询股票公告。

**请求路径**

`/api/Disclosure/stock`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 公告发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 公告发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `search` | query/body/form | `string` | 否 | 股票代码、股票名称、公告类型名或标题模糊搜索 |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `typeid` | query/body/form | `string` | 否 | 公告类型 ID，支持多值 |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `CompId` | `number` | 公告复合 ID，可用于下载 `infoid` |
| `Title` | `string` | 公告标题 |
| `PublishDate` | `string` | 发布日期 |
| `SecCode` / `SecName` | `string/string` | 证券代码与名称 |
| `Disclosure_Type` / `Disclosure_Name` | `string/string` | 披露大类编码与名称 |
| `Type` / `TypeName` | `string/string` | 一级公告类型 |
| `Type2` / `Type2Name` | `string/string` | 二级公告类型 |
| `ReleSecCode` | `string` | 关联证券代码 |
| `FileType` | `string` | 文件类型 |
| `FileSize` | `number` | 文件大小 |
| `CreateTime` | `string` | 入库时间 |

## 预披露公告查询 `GET/POST /api/Disclosure/pre`

**接口描述**

按日期、公司名称与标题关键词分页查询预披露公告。

**请求路径**

`/api/Disclosure/pre`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `search` | query/body/form | `string` | 否 | 公司名称或标题模糊搜索 |
| `keyword` | query/body/form | `string` | 否 | 标题或公司名称关键词 |
| `comname` | query/body/form | `string` | 否 | 公司全称精确匹配 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`CompId`、`Title`、`PublishDate`、`CreateTime`、`FileType`、`FileSize`、`OriginName`、`CompanyName`。

## IR 互动问答查询 `GET/POST /api/Disclosure/irqna`

**接口描述**

按日期、证券代码、关键词分页查询 IR 互动问答。

**请求路径**

`/api/Disclosure/irqna`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 回复时间下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 回复时间上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `search` | query/body/form | `string` | 否 | 证券代码、证券名称、问题或回复模糊搜索 |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `keyword` | query/body/form | `string` | 否 | 问题或回复关键词 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`InfoId`、`SecCode`、`SecName`、`Exchange`、`Question`、`Reply`、`QuestionTime`、`ReplyTime`、`Source`。

## 调研记录查询 `GET/POST /api/Disclosure/iractivity`

**接口描述**

按日期、证券代码与标题关键词分页查询 调研记录。

**请求路径**

`/api/Disclosure/iractivity`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `search` | query/body/form | `string` | 否 | 证券代码、证券名称或标题模糊搜索 |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`CompId`、`Title`、`SecCode`、`SecName`、`PublishDate`、`CreateTime`、`FileType`、`FileSize`、`TypeName`。

## 公司声音查询 `GET/POST /api/Disclosure/voice`

**接口描述**

按日期、证券代码、公司名称或内容关键词分页查询公司声音。

**请求路径**

`/api/Disclosure/voice`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `search` | query/body/form | `string` | 否 | 证券代码、公司简称或内容模糊搜索 |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `keyword` | query/body/form | `string` | 否 | 内容或公司简称关键词 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`CompId`、`SecCode`、`SecName`、`Content`、`PublishDate`。

## 股票新闻查询 `GET/POST /api/News/stock`

**接口描述**

按日期、证券代码、标题关键词和来源分页查询股票新闻。

**请求路径**

`/api/News/stock`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源；前缀反引号可表示精确匹配，如 `` `新华社`` |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`NewsId`、`TaskID`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`CreateTime`、`TypeName`、`SecCode`、`SecName`、`Publisher`、`BriefText`。

## 股票新闻详情 `GET /api/News/stock/{id}`

**接口描述**

按股票新闻 ID 查询详情。

**请求路径**

`/api/News/stock/{id}`

**请求方法**

`GET`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | `number` | 是 | 新闻 ID |
| `brief` | query | `number` | 否 | `1` 返回正文 `Article` |
| `apikey` | query | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `ObjectDataResult`。`data` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`SecCode`、`SecName`、`Publisher`、`Article`。

## 期货新闻查询 `GET/POST /api/News/future`

**接口描述**

按日期、标题关键词、来源、栏目类型和品种分页查询期货新闻。

**请求路径**

`/api/News/future`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源模糊匹配 |
| `newstype` | query/body/form | `string` | 否 | 栏目类型，支持多值；常见值 `jrqh`、`jysgg`、`gjqs`、`jgyj`、`jgbg`、`pzzx` |
| `commodity` | query/body/form | `string` | 否 | 品种名称关键词 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`TypeID`、`TypeName`、`Commodity`、`BriefText`。

## 期货新闻详情 `GET /api/News/future/{id}`

**接口描述**

按期货新闻 ID 查询详情。

**请求路径**

`/api/News/future/{id}`

**请求方法**

`GET`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | path | `number` | 是 | 新闻 ID |
| `brief` | query | `number` | 否 | `1` 返回正文 `Article` |
| `apikey` | query | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `ObjectDataResult`。`data` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`TypeID`、`TypeName`、`Commodity`、`Exchange`、`Article`。

## 政府工作新闻查询 `GET/POST /api/News/gov`

**接口描述**

按日期、标题关键词、来源、新闻类型、机构与发布单位分页查询政府工作新闻。

**请求路径**

`/api/News/gov`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源；前缀反引号可表示精确匹配 |
| `newstype` | query/body/form | `string` | 否 | 新闻类型编码或名称，支持多值 |
| `organid` | query/body/form | `string` | 否 | 机构 ID，支持前缀匹配；前缀反引号可表示精确匹配 |
| `infopub` | query/body/form | `string` | 否 | 发布单位精确匹配 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`NewsId`、`TaskID`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`CreateTime`、`TypeName`、`TypeID`、`OrganName`、`OrganID`、`InfoPub`、`HaveAttach`、`BriefText`。

## 政府工作新闻详情 `GET /api/News/gov/{id}`

**接口描述**

按政府工作新闻 ID 查询详情，并将附件 HTML 链接整理为数组。

**请求路径**

`/api/News/gov/{id}`

**请求方法**

`GET`

**返回结构**

返回 `ObjectDataResult`。`data` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`TypeName`、`OrganName`、`InfoPub`、`Attach_Store`、`Article`。

`Attach_Store[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `url` | `string` | 附件地址 |
| `name` | `string` | 附件名称 |

## 行业新闻查询 `GET/POST /api/News/industry`

**接口描述**

按日期、标题关键词、来源、新闻类型和行业 ID 分页查询行业新闻。

**请求路径**

`/api/News/industry`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源；前缀反引号可表示精确匹配 |
| `newstype` | query/body/form | `string` | 否 | 新闻类型，支持多值 |
| `industryid` | query/body/form | `string` | 否 | 行业 ID，支持多值和前缀匹配 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`NewsId`、`TaskID`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`CreateTime`、`TypeName`、`Publisher`、`BriefText`。

## 行业新闻详情 `GET /api/News/industry/{id}`

**接口描述**

按行业新闻 ID 查询详情。

**请求路径**

`/api/News/industry/{id}`

**请求方法**

`GET`

**返回结构**

返回 `ObjectDataResult`。`data` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`TypeName`、`Publisher`、`Article`。

## 宏观新闻查询 `GET/POST /api/News/macro`

**接口描述**

按日期、标题关键词、来源和新闻类型分页查询宏观新闻。

**请求路径**

`/api/News/macro`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布日期下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布日期上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源；前缀反引号可表示精确匹配 |
| `newstype` | query/body/form | `string` | 否 | 类型编码，支持多值；`00` 表示不过滤 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：`NewsId`、`TaskID`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`CreateTime`、`TypeID`、`TypeName`、`Publisher`、`BriefText`。

## 宏观新闻详情 `GET /api/News/macro/{id}`

**接口描述**

按宏观新闻 ID 查询详情。

**请求路径**

`/api/News/macro/{id}`

**请求方法**

`GET`

**返回结构**

返回 `ObjectDataResult`。`data` 字段：`NewsId`、`Title`、`SourceName`、`HttpUrl`、`PublishDate`、`TypeName`、`Publisher`、`Article`。

## 负面新闻查询 `GET/POST /api/News/neg`

**接口描述**

查询公司、行业与宏观负面新闻。返回结果会将底层不同来源统一整理为前端友好的结构。

**请求路径**

`/api/News/neg`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `startdate` | query/body/form | `string` | 否 | 发布时间下界；日期未传时默认向前取配置月数 |
| `enddate` | query/body/form | `string` | 否 | 发布时间上界 |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号 |
| `brief` | query/body/form | `number` | 否 | `1` 返回 `BriefText` |
| `stock` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔；传该条件时仅查公司负面 |
| `alert` | query/body/form | `string` | 否 | 预警类别 ID，多个用 `,` 或 `;` 分隔；传该条件时仅查公司负面 |
| `important` | query/body/form | `string` | 否 | 重要性：`100`、`101`、`102`、`103` |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `source` | query/body/form | `string` | 否 | 新闻来源模糊匹配 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `NewsId` | `number` | 复合新闻 ID；详情查询必须使用该值 |
| `PublishDate` | `string` | 发布日期 |
| `PublishTime` | `string` | 发布时间 |
| `Title` | `string` | 标题 |
| `SourceName` | `string` | 来源 |
| `Author` | `string` | 作者 |
| `TypeCode` | `string \| null` | 负面类型编码 |
| `CategoryName` | `string` | `公司负面`、`行业负面` 或 `宏观负面` |
| `BriefText` | `string \| null` | `brief=1` 时返回截断正文 |
| `SecAlertList` | `SecAlertItem[] \| null` | 公司负面关联证券与预警信息 |
| `IndustryList` | `IndustryItem[] \| null` | 行业负面关联行业信息 |

`SecAlertList[]` 字段：`Alert`、`Important`、`SecCode`、`SecName`、`AlertId`、`CompanyName`。

`IndustryList[]` 字段：`Code`、`Name`。

## 负面新闻详情 `GET /api/News/neg/{id}`

**接口描述**

按负面新闻复合 ID 查询详情。复合 ID 来自列表返回的 `NewsId`。

**请求路径**

`/api/News/neg/{id}`

**请求方法**

`GET`

**返回结构**

返回 `ObjectDataResult`。`data` 字段与负面新闻列表基本一致，`brief=1` 时额外返回 `Article` 正文。

## 申万精品摘要内容查询 `GET/POST /api/PremiumInfo/brief`

**接口描述**

按资讯类别与 ID 查询单条申万精品资讯的摘要内容。

**请求路径**

`/api/PremiumInfo/brief`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `apikey` | query/form/header | `string` | 条件 | API Key |
| `ntype` | query/body/form | `number` | 是 | 资讯类别：`0`-利好，`1`-负面，`2`-重要公告，`3`-焦点研报(个股)，`4`-聚焦视点，`5`-焦点研报(行业) |
| `nid` | query/body/form | `number` | 是 | 资讯 ID |

**返回结构**

返回 `ObjectDataResult`。`data` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `number` | 资讯 ID |
| `brief` | `string` | 摘要内容（HTML 格式） |

<details>
<summary>调用示例</summary>

```http
GET /api/PremiumInfo/brief?ntype=0&nid=12345 HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```json
{
  "data": {
    "id": 12345,
    "brief": "<p>公司发布2025年度报告...</p>"
  }
}
```

</details>

## 申万精品资讯列表查询 `GET/POST /api/PremiumInfo/list`

**接口描述**

按资讯类别分页查询申万精品资讯列表，支持基于游标的上拉加载更多与下拉刷新最新两种分页方式。

**请求路径**

`/api/PremiumInfo/list`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `apikey` | query/form/header | `string` | 条件 | API Key |
| `ntype` | query/body/form | `number` | 是 | 资讯类别：`0`-利好，`1`-负面，`2`-重要公告，`3`-焦点研报(个股)，`4`-聚焦视点，`5`-焦点研报(行业) |
| `late` | query/body/form | `number` | 否 | 「查询最新」的开始游标（不含此记录），返回晚于此游标的所有记录。与 `more` 互斥。值使用返回结果中的 `tid` |
| `more` | query/body/form | `number` | 否 | 「查询更多」的开始游标（不含此记录），返回早于此游标的记录。为空时返回最新记录。与 `late` 互斥。值使用返回结果中的 `tid` |
| `psize` | query/body/form | `number` | 条件 | 每页返回记录数，仅在「查询更多」模式下有效且必需，最大 `500` |
| `brief` | query/body/form | `number` | 否 | `1`-含摘要（截断），`2`-含摘要（全部），`0`-不含摘要 |

**分页方式说明**

- **查询最新（`late`）**：传入上次返回的最新 `tid`，获取晚于该记录的所有新数据，不分页
- **查询更多（`more`）**：传入上次返回的最早 `tid`，分页获取更早的历史数据。不传 `more` 时返回最新的一页

**返回结构**

返回 `PagedRowsResult`。`rows[]` 通用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `number` | 资讯 ID |
| `pubdate` | `string` | 发布日期 |
| `tid` | `number` | 组合游标 ID，用于 `late`/`more` 分页参数 |

各 `ntype` 特有字段：

| ntype | 说明 | 特有字段 |
| --- | --- | --- |
| `0` | 利好 | `scode`、`sname`、`grade`、`imp`、`industryid`、`industryname`、`title`、`source` |
| `1` | 负面 | `scode`、`sname`、`grade`、`imp`、`industryid`、`industryname`、`title`、`source` |
| `2` | 重要公告 | `scode`、`sname`、`stype`、`imp`、`title` |
| `3` | 焦点研报(个股) | `scode`、`sname`、`grade`、`imp`、`orgid`、`orgname`、`industryid`、`industryname`、`title`、`reportid` |
| `4` | 聚焦视点 | `title`、`source`、`url` |
| `5` | 焦点研报(行业) | `industryid`、`industryname`、`grade`、`imp`、`orgid`、`orgname`、`title`、`reportid`、`stocks`(关联股票数组) |

`ntype=5` 时 `stocks[]` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | `string` | 证券代码 |
| `name` | `string` | 证券名称 |

`brief=1` 时返回的 `brief` 字段为纯文本（已去除 HTML 标签）并截断至配置字数。

<details>
<summary>调用示例</summary>

```http
GET /api/PremiumInfo/list?ntype=0&psize=20&brief=1 HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```json
{
  "reccount": null,
  "psize": 20,
  "pno": null,
  "rows": [
    {
      "id": 12345,
      "scode": "600000",
      "sname": "浦发银行",
      "grade": "买入",
      "imp": 3,
      "industryid": "010100",
      "industryname": "银行",
      "title": "浦发银行2025年报点评",
      "source": "某证券研究所",
      "pubdate": "2026-05-15",
      "brief": "公司发布2025年度报告，实现营业收入...",
      "tid": 12345000020260515
    }
  ]
}
```

</details>

## 混合资讯列表查询 `GET/POST /api/CompInfo/list`

**接口描述**

汇总查询与指定股票相关的多种资讯（研报、公告、新闻、调研记录、负面新闻），一次请求获取多维度资讯。

**请求路径**

`/api/CompInfo/list`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `apikey` | query/form/header | `string` | 条件 | API Key |
| `stocks` | query/body/form | `string` | 否 | 证券代码，多个用 `,` 或 `;` 分隔 |
| `infotype` | query/body/form | `string` | 否 | 资讯类别筛选（`EnumContentType` 值），多个用 `,` 或 `;` 分隔，`0` 或不传表示全部可用类型 |
| `keyword` | query/body/form | `string` | 否 | 标题关键词 |
| `startdate` | query/body/form | `string` | 否 | 查询开始日期。当所有查询条件（stocks/infotype/keyword/日期）均为空时，自动使用短日期范围（默认最近 1 个月） |
| `enddate` | query/body/form | `string` | 否 | 查询结束日期 |
| `brief` | query/body/form | `number` | 否 | `1` 返回摘要 `BriefText` |
| `wx` | query/body/form | `boolean` | 否 | 是否包含微信公众号研报，默认 `true` |
| `psize` | query/body/form | `number` | 是 | 每页记录数，最大 `200` |
| `pno` | query/body/form | `number` | 否 | 页号，从 `1` 开始 |

**infotype 可选值**

| 值 | 对应资讯类型 |
| --- | --- |
| `0` 或不传 | 全部可用类型 |
| `1` | 研究报告 |
| `6` | 公司新闻 |
| `7` | 股票公告 |
| `11` | 调研记录 |
| `16` | 负面新闻 |

**返回结构**

返回 `PagedRowsResult`。`rows[]` 通用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `nID` | `number` | 资讯 ID |
| `nType` | `number` | 资讯类别（`EnumContentType` 值：`1`-研报，`6`-新闻，`7`-公告，`11`-调研记录，`16`-负面新闻） |
| `PublishDate` | `string` | 发布日期 |
| `Title` | `string` | 标题 |
| `Attr` | `string` | 属性标记 |
| `StkCode` | `string` | 证券代码 |
| `Market` | `string` | 市场（`SH`/`SZ`/`BJ`/`HK`） |
| `StkName` | `string` | 证券名称 |
| `NewFlag` | `number` | 是否 7 日内新增，`1`-是 |
| `BriefText` | `string \| null` | `brief=1` 时返回摘要（负面新闻已去除 HTML，公告已规范化空白） |
| `Properties` | `object \| null` | 各类型资讯的附加属性（见下表） |

**各 nType 对应的 Properties**

| nType | Properties 字段 |
| --- | --- |
| `1` 研报 | `instname`(机构名)、`author`(作者)、`isstar`(是否明星分析师)、`filemode`、`kind`(一级分类)、`kind2`(二级分类)、`indname`(行业名)、`page`(页数) |
| `6` 新闻 | 无附加属性 |
| `7` 公告 | `typename`(一级公告类型)、`type2name`(二级公告类型)、`filemode`(文件类型) |
| `11` 调研记录 | `complexid`(复合ID)、`typename`(类型名)、`filemode`(文件类型) |
| `16` 负面新闻 | `complexid`(复合ID)、`source`(来源)、`imp`(重要性分数)、`alert`(预警类别名)、`alertid`(预警类别ID) |

<details>
<summary>调用示例</summary>

```http
GET /api/CompInfo/list?stocks=600000&psize=20&brief=1 HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```json
{
  "reccount": 256,
  "psize": 20,
  "pno": 1,
  "rows": [
    {
      "nID": 12345,
      "nType": 1,
      "PublishDate": "2026-05-15",
      "Title": "浦发银行2025年报点评",
      "Attr": "",
      "StkCode": "600000",
      "Market": "SH",
      "StkName": "浦发银行",
      "NewFlag": 1,
      "BriefText": "公司发布2025年度报告，实现营业收入...",
      "Properties": {
        "instname": "某证券研究所",
        "author": "张三",
        "isstar": true,
        "filemode": 1,
        "kind": "银行",
        "kind2": "股份制银行",
        "indname": "银行",
        "page": 25
      }
    }
  ]
}
```

</details>

## 文件下载 `GET/POST /api/Download`

**接口描述**

按资讯类别与资讯 ID 下载附件。接口可能返回文件流、HTTP 代理文件流、重定向，或在预检模式下返回 JSON。

**请求路径**

`/api/Download`

**请求方法**

`GET`、`POST`

**请求参数**

| 参数 | 位置 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| `infotype` | query/body/form | `number` | 是 | 资讯类别。当前下载逻辑支持 `1` 研报、`7` 股票公告、`9` 预披露公告、`11` 调研记录 |
| `infoid` | query/body/form | `number` | 是 | 资讯 ID，如 `ReportID` 或 `CompId` |
| `browse` | query/body/form | `number` | 否 | `1` 按浏览方式响应；默认按附件下载方式响应 |
| `precheck` | query/body/form | `boolean` | 否 | `true` 仅做授权、参数与文件存在性预检 |
| `dtype` | query/body/form | `number` | 否 | 附加文件类型：空为原文；`0` 原文缩略图；`1` 公众号快照；`2` 中文译文；`3` 中英对照译文 |
| `apikey` | query/form | `string` | 条件 | API Key；使用请求头鉴权时可不传 |

**返回结构**

- 普通下载：返回文件流，可能包含 `Content-Disposition`、`Content-Type`、`Content-Range` 等响应头
- HTTP 远端文件：服务端代理远端文件流
- 微信公众号原文：可能返回 `302` 重定向
- `precheck=true` 且通过：返回 `{ "success": true }`

<details>
<summary>调用示例</summary>

```http
GET /api/Download?infotype=1&infoid=123456&dtype=2 HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```http
GET /api/Download?infotype=7&infoid=98765&precheck=true HTTP/1.1
Host: localhost:5000
Authorization: Bearer your-api-key
```

```json
{
  "success": true
}
```

</details>


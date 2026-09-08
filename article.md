本文介绍存在突发流量的业务如何通过简单改造业务代码，避免因为突发流量导致限流，保障请求成功率。

<span id="263ca129"></span>
# 什么是限流

方舟模型服务 API 会对单位时间内的请求次数、token 使用量、使用量的增长幅度及同时发起的请求数量进行限制，以保障服务的稳定运行和资源的合理分配。当调用方发起的请求触发 API 的限流，会返回 “429: 'Too Many Requests'” 错误。

<span id="1dd597ae"></span>
## 为什么有限流

大模型服务因模型参数量庞大（数十亿至千亿级），**算力成本高昂及扩容周期更长**，导致业界模型服务平台面临流量承接能力（尤其是突发流量）不足的问题。在此背景下，平台会**尽最大努力提升请求成功率**，保障模型服务的整体可用性。限流作为请求的第一层流量防护机制，主要作用如下：


* **减少 API 滥用或者误用**：恶意攻击会给服务器发送大量请求，试图让服务过载导致服务中断。方舟设置速率限制，可以有效防止此类情况。

* **保障用户公平地访问**：避免个人或者组织发送过多请求，导致其他人的服务访问和响应速度减慢。通过限制单个用户的请求通量（单位时间请求量），确保尽可能多的人能正常使用API，减少 API 服务速度变慢情况。

* **帮助控制平台总体负载**：如果 API 服务请求极速增加，可能会给服务端资源带来很大扩容压力，导致性能问题。通过设置限流，可以帮助所有用户保持流畅、稳定的体验。


<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">注意</div>


<div data-tips="true" data-tips-type="warning">限流是<strong>单位时间服务用量的上限</strong>，而<strong>非服务用量的刚性保障</strong>。当任务量突增（如突发流量）或持续高负载时，仍可能触发限流。为了尽可能用好限流配额，避免失败请求占据限流配额，建议用户主动平滑流量曲线或做好模型间的流量分流等。</div>


<span id="2c72dafc"></span>
## 限流对象

当前方舟的限流对象主要有：


* **模型限流**：同主账号下，同模型（不区分版本）限流，由方舟设定，不可手动调整，各个模型默认限流信息请参见 [模型列表](https://www.volcengine.com/docs/82379/1330310)。如有超额的流量需求，请通过[工单](https://console.volcengine.com/workorder/create?step=2&SubProductID=P00001166)提交提额申请。

* **推理接入点限流**：推理接入点（Endpoint）限流，作用于推理接入点，用户可以自行调整，用于灵活控制应用的模型服务使用量。


<span id="3ac6ff03"></span>
## 限流类型

方舟提供了不同的限流指标。


<span aceTableMode="list" aceTableWidth="2,4,3"></span>
|限流类型 |解释说明 |适用对象 |
|---|---|---|
|TPM |每分钟可以处理的 token 量限制，包含模型的输入和输出。 |通常是在线推理中按 token 计费模型的模型服务的限流指标。 |
|TPD |每天可以处理的 token 量限制，包含模型的输入和输出。 |通常是批量处理的模型服务的限流指标。 |
|RPM |每分钟可发起的请求量限制，用以防 Dos 攻击。 |几乎所有模型都有对应 RPM 指标。 |
|IPM |每分钟可生成的图片数量限制，面向生图模型。 |通常是图片生成模型的模型服务的限流指标。 |
|Inflight Batchsize |并行在途请求数，同主账号下指定模型同时在处理的请求数量限制，在途请求包括排队、数据传输、计算处理、数据回传全流程的请求。 |几乎所有模型都有对应的并发数指标。 |


<span id="344965cc"></span>
## 限流错误码

> 详细方舟错误码见 [错误码](https://www.volcengine.com/docs/82379/1299023)。


<span id="3376f097"></span>
# 什么是突发流量

在单位时间内请求量产生剧烈波动，常见在定时数据处理任务、热点事件等场景，平台会根据**请求特征、资源水位、模型特征、用户历史流量**等因素认定突发流量（通常情况下，建议您将 Token 用量的增长速率控制在每 3 分钟 20% 以内）。


<span aceTableMode="list" aceTableWidth="3,3"></span>
|突发流量示意图 |说明 |
|---|---|
|<span>![图片](https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/77f12271fa144237ac9bb1ca92331b96~tplv-goo7wpa0wc-image.image) </span> |**常见行为**<br><br><br>* 发送请求频率加快<br><br>* 发送请求的输入或输出长度突然变长等**监控图标（TPM、RPM）** <br><br>* 控制台： [在线推理](https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint) \> 推理接入点的详情页 \> **监控** 页签 |


<span id="b648a7e8"></span>
# 平台处理策略

针对突发流量场景，平台采取以下策略**提升推理请求成功率**：


* 快速扩容指定模型的服务集群，以逐步承载住服务。

* 方舟会在用户可容忍的超时时间内，通过服务端重试爬坡策略提升请求成功率。

* 当突发流量抢占过多资源影响整体服务可用性时，平台将优先限制/熔断突发流量，保障其他用户的可用性。

* 在触发限制和熔断时，方舟会对突增的请求返回 “429: 'Too Many Requests'” 错误信息，并在资源扩容到一定程度后（分钟级）逐步恢复。



错误码信息 


<span aceTableMode="list" aceTableWidth="2,2,3,4,4"></span>
|状态码 |错误类型 |错误码 |错误信息 |含义 |
|---|---|---|---|---|
|429 |TooManyRequests |ServerOverloaded |The service is currently unable to handle additional requests due to server overload. Please retry later. Request ID: |服务资源紧张，请您稍后重试。常出现在调用流量突增或刚开始调用长时间未使用的推理接入点。<br><br><div data-tips="true" data-tips-type="tip" data-tips-is-title="true">说明</div><br><br><br><div data-tips="true" data-tips-type="tip">调用<code>doubao-seed-1-8</code>及之前版本模型触发突增流量限制时，返回此错误码。</div><br> |
|429 |TooManyRequests |RequestBurstTooFast |System protection triggered by request burst. Please slow down traffic growth and increase requests gradually before retrying. |请求量激增触发系统保护，请放缓流量提升速度，逐步增加请求量后再尝试<br><br><div data-tips="true" data-tips-type="tip" data-tips-is-title="true">说明</div><br><br><br><div data-tips="true" data-tips-type="tip">调用 <code>doubao-seed-2-0</code>及之后版本模型触发突增流量限制时，返回此错误码。</div><br> |



&nbsp;

<span id="6d6ad180"></span>
# 客户端处理策略

业务评估存在突发流量限流情况，推荐以下主动优化策略，进一步提升请求成功率并规避限流风险。


* **客户端整流，主动平滑流量曲线**：通过缓冲机制（如消息队列、本地任务队列）将瞬时突发流量转化为低波动请求，控制对平台的流量增长斜率。从源头避免因斜率过高触发`ServerOverloaded`错误。

* **客户端分流，跨模型负载均衡**：利用方舟多模型的独立突发容忍能力，将流量分散至多个具备冗余容量的模型，避免单一模型资源耗尽。


<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">注意</div>



* <div data-tips="true" data-tips-type="warning">仅支持跨模型分流（如同时调用“模型A”和“模型B”）：不同模型的资源池相互独立，可分散流量压力；</div>


* <div data-tips="true" data-tips-type="warning">同模型多Endpoint/多账号分流无效：同一模型的所有推理接入点和账号共享同一个底层计算资源池，流量最终会汇聚到同一资源池，无法规避该模型的限流阈值。</div>


* **购买模型单元，主动扩容资源池**：购买模型单元，预测自己的流量波动趋势，提前15分钟下单扩容购买模型单元，用扩容到的模型单元来承接自己的突发增量。


策略选择建议


<span aceTableMode="list" aceTableWidth="2,2,3"></span>
|业务场景 |推荐组合策略 |方舟能力支撑点 |
|---|---|---|
|不可预测瞬时峰值（热点事件） |整流+分流 |动态容限曲线+多模型资源隔离 |
|可预测周期性突发（定时任务） |分流+购买模型单元 |提前15分钟扩容+独立资源池 |
|高稳定性要求核心业务 |整流为主+购买备用单元 |稳定承载区间+资源优先级保障 |


<span id="ac524fd3"></span>
## 实践 通过 header 配置（推荐）

对于无需即时完成的推理请求，可以通过请求 **header** 字段传入标识。方舟服务端会检测对应标识，尽可能在指定时间响应请求。

> 平台对配置了 header 排队标识的突发流量请求，会按照策略重试排队中的请求，直到请求开始处理或者排队超时。对比普通请求来说，在触发突发流量限流时，不是直接报错，而是在排队时间内帮用户进行重试。


<span id="d6071128"></span>
### 核心配置


<span aceTableMode="list" aceTableWidth="2,2,3"></span>
|header 字段 |示例 |说明 |
|---|---|---|
|X\-Ark\-Max\-Wait\-Timeout\-Ms |300000 |突发请求的最大排队时间。<br><br>单位：毫秒<br><br>建议值：[60000,600000]，1~10分钟<br><br>常见配置：<br><br><br>* 60000：1分钟<br><br>* 180000：3分钟<br><br>* 300000：5分钟<br><br>* 600000: 10分钟 |


<span id="26cc0670"></span>
### 超时时间配置

长请求（深度思考、长输入输出）需关注超时时间，避免因叠加了排队时间，客户端超时关闭连接，导致请求失败。

**非流式请求**（`stream：false`）


* 超时时间：`原基础超时时间（非突发场景）`+`突发请求最大排队时间`


**流式请求**（`stream：true`）


* 超时时间：\> `突发请求最大排队时间`

> 注意：如使用方舟 Go SDK ，流式输出请求超时时间也需设置 `原基础超时时间（非突发场景）`+ `突发请求最大排队时间`


**举例**

请求原基础超时时间（非突发场景下） 30 分钟，突发请求最大排队时间 5 分钟。


* 非流式输出超时时间： 35 分钟

* 流式输出的请求超时时间

   * 方舟 Python/Java SDK：大于 5 分钟（ SDK 默认超时时间 10 分钟，无需重新配置）

> 注意：如使用方舟 Go SDK ，流式输出请求超时时间也需设置 35 分钟


<span id="cea33477"></span>
### 示例代码


示例代码


<Tabs>
<Tab zoneid="lLOY5KtNBS" title="Python">
<TabTitle>Python</TabTitle>

```Python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    api_key=os.environ.get("ARK_API_KEY"),
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    # 非流式输出：超时时间 = 排队时间 + 基础超时时间 = 300 秒 + 1800秒 
    timeout=2100, 
)

completion = client.chat.completions.create(
    # Replace with Model ID
    model="doubao-seed-2-1-pro-260628",
    messages = [
        {"role": "user", "content": "常见的十字花科植物有哪些？"},
    ],
    # 自定义request，突发流量最大排队时间 300000 毫秒（5分钟）
    extra_headers={"X-Ark-Max-Wait-Timeout-Ms": "300000"},
    stream = False,
)
print(completion.choices[0].message.content)
```



</Tab>
<Tab zoneid="rJ6nDGSwY6" title="Go">
<TabTitle>Go</TabTitle>

```Go
package main

import (
  "context"
  "fmt"
  "log"
  "os"
  "time"

  "github.com/volcengine/volcengine-go-sdk/service/arkruntime"
  "github.com/volcengine/volcengine-go-sdk/service/arkruntime/model"
  "github.com/volcengine/volcengine-go-sdk/volcengine"
)

const (
  ArkModel   = "doubao-seed-2-1-pro-260628"
  ArkBaseUrl = "https://ark.cn-beijing.volces.com/api/v3"
)

var (
  ArkApiKey = os.Getenv("ARK_API_KEY")
)

func callArk(msg string) (string, error) {
  client := arkruntime.NewClientWithApiKey(
    ArkApiKey,
    arkruntime.WithBaseUrl(ArkBaseUrl),
  )
  
  // 非流式输出：超时时间 = 排队时间 + 基础超时时间 = 300 秒 + 1800秒
  ctx, cancel := context.WithTimeout(context.Background(), 2100*time.Second)
  defer cancel()

  resp, err := client.CreateChatCompletion(
    ctx,
    model.ChatCompletionRequest{
      Model: ArkModel,
      Messages: []*model.ChatCompletionMessage{
        {
          Role: model.ChatMessageRoleUser,
          Content: &model.ChatCompletionMessageContent{
            StringValue: volcengine.String(msg),
          },
        },
      },
    },
    arkruntime.WithCustomHeaders(map[string]string{
      // 自定义request，突发流量最大排队时间 300000 毫秒 （5分钟）
      "X-Ark-Max-Wait-Timeout-Ms": "300000",
    }),
  )
  if err != nil {
    return "", err
  }

  if len(resp.Choices) > 0 && resp.Choices[0].Message.Content != nil {
    return *resp.Choices[0].Message.Content.StringValue, nil
  }
  return "", fmt.Errorf("empty response")
}

func main() {
  result, err := callArk("常见的十字花科植物有哪些？")
  if err != nil {
    log.Fatalf("调用失败: %v", err)
  }

  fmt.Println(result)
}
```



</Tab>
<Tab zoneid="rmf5yO5ctN" title="Java">
<TabTitle>Java</TabTitle>

```Java
package com.ark.sample;

import com.volcengine.ark.runtime.model.completion.chat.ChatCompletionRequest;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessage;
import com.volcengine.ark.runtime.model.completion.chat.ChatMessageRole;
import com.volcengine.ark.runtime.service.ArkService;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class Header {
    private static final String ARK_MODEL = "doubao-seed-2-1-pro-260628";
    private static final String ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3";
    private static final String ARK_API_KEY = System.getenv("ARK_API_KEY");

    public static String callArk(String msg) {
        ArkService service = ArkService.builder()
                .apiKey(ARK_API_KEY)
                .baseUrl(ARK_BASE_URL)
                // 非流式输出：超时时间 = 排队时间 + 基础超时时间 = 300 秒 + 1800秒
                .timeout(Duration.ofSeconds(2100))
                .build();

        final List<ChatMessage> messages = new ArrayList<>();
        final ChatMessage userMessage = ChatMessage.builder()
                .role(ChatMessageRole.USER)
                .content(msg)
                .build();
        messages.add(userMessage);

        ChatCompletionRequest chatCompletionRequest = ChatCompletionRequest.builder()
                .model(ARK_MODEL)
                .messages(messages)
                .build();

        Map<String, String> customHeaders = new HashMap<>();
        // 自定义request，突发流量最大排队时间 300000 毫秒 （5分钟）
        customHeaders.put("X-Ark-Max-Wait-Timeout-Ms", "300000");

        String result = (String) service.createChatCompletion(chatCompletionRequest, customHeaders)
                .getChoices()
                .get(0)
                .getMessage()
                .getContent();


        service.shutdownExecutor();
        return result;
    }

    public static void main(String[] args) {
        try {
            String result = callArk("常见的十字花科植物有哪些？");
            System.out.println(result);
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
```



</Tab>
</Tabs>



&nbsp;

<span id="2f7ffc8d"></span>
## 实践 客户端削峰填谷

<span id="ec26b081"></span>
### 设计逻辑

`Client端突发峰值请求 → MQ无限制接收（削峰） → 消费端斜率可控匀速消费（填谷） → 方舟SDK调用大模型`


1. **削峰**：RabbitMQ 做流量蓄水池，生产者无任何速率限制，承接所有瞬时峰值请求，彻底隔离峰值与大模型服务；

2. **填谷**：消费端以平稳速率消费 MQ 积压请求，充分利用大模型服务能力，无资源浪费；

3. **斜率可控**：消费速率从`5QPS`开始，**每 5 秒增长 2QPS**，直到 30QPS 封顶，增长斜率恒定，无任何陡增，不会打满大模型服务；

4. **可靠性**：MQ 队列 + 消息持久化、手动 ACK 确认，消息零丢失；失败请求自动重回队列重试。



示例代码


<Tabs>
<Tab zoneid="IeqlGcihgT" title="Python">
<TabTitle>Python</TabTitle>

```Python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import json
import os
import threading
# 安装SDK:  pip install 'volcengine-python-sdk[ark]' pika
from volcenginesdkarkruntime import Ark
import pika

# ===================== 全局极简配置【所有参数可一键修改】=====================
MQ_QUEUE = "client_ark_queue"  # MQ削峰队列
MQ_CONF = pika.ConnectionParameters('127.0.0.1', 5672, credentials=pika.PlainCredentials('guest', 'guest'))
ARK_API_KEY = os.getenv('ARK_API_KEY')  # 获取API Key: https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
ARK_MODEL = "doubao-seed-2-1-pro-260628"  
# 🔥 斜率可控核心配置 🔥 斜率=步长/间隔 = 2/5 = 0.4QPS/秒，绝对无陡增
FLOW = {"curr_qps": 5, "max_qps": 30, "step": 2, "interval": 5, "count": 0}
LOCK = threading.Lock()

# ===================== 1. 极简斜率可控流控【核心】=====================
def flow_schedule():
    """后台线程：匀速增长消费速率，控制斜率"""
    while True:
        time.sleep(FLOW["interval"])
        if FLOW["curr_qps"] < FLOW["max_qps"]:
            FLOW["curr_qps"] += FLOW["step"]

def reset_count():
    """后台线程：每秒重置请求计数器，精准控QPS"""
    while True:
        time.sleep(1)
        with LOCK: FLOW["count"] = 0

def allow():
    """流控校验：是否允许发起本次请求"""
    with LOCK:
        if FLOW["count"] < FLOW["curr_qps"]:
            FLOW["count"] += 1
            return True
    return False

# ===================== 2. MQ生产者【Client端请求投递，削峰】=====================
def producer(client_req):
    """投递Client请求到MQ，无速率限制，承接峰值流量"""
    conn = pika.BlockingConnection(MQ_CONF)
    ch = conn.channel()
    ch.queue_declare(queue=MQ_QUEUE, durable=True)  # 队列持久化
    ch.basic_publish(exchange='', routing_key=MQ_QUEUE, body=json.dumps(client_req),
                     properties=pika.BasicProperties(delivery_mode=2))  # 消息持久化
    conn.close()

# ===================== 3. 方舟SDK调用【大模型请求核心】=====================
def call_ark(msg):
    """✅ 标准使用指定方舟SDK，极简调用大模型"""
    client = Ark(api_key=ARK_API_KEY,base_url='https://ark.cn-beijing.volces.com/api/v3',)
    resp = client.chat.completions.create(model=ARK_MODEL, messages=[{"role": "user", "content": msg}])
    return resp.choices[0].message.content

# ===================== 4. MQ消费者【填谷+斜率控速+调用方舟，核心主逻辑】=====================
def consumer():
    """消费端核心：削峰后的流量，斜率可控匀速消费，调用方舟大模型"""
    conn = pika.BlockingConnection(MQ_CONF)
    ch = conn.channel()
    ch.queue_declare(queue=MQ_QUEUE, durable=True)
    ch.basic_qos(prefetch_count=1)  # 防止消费积压

    def callback(_ch, method, _, body):
        req = json.loads(body)["msg"]
        if not allow():  # 流控校验，不通过则消息重回队列
            _ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return
        try:
            ark_resp = call_ark(req)  # 调用方舟大模型
            print(f"请求:{req[:15]} | 响应:{ark_resp[:20]}")
            _ch.basic_ack(delivery_tag=method.delivery_tag)  # 消费成功手动ACK
        except Exception as e:
            _ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)  # 失败重试

    ch.basic_consume(queue=MQ_QUEUE, on_message_callback=callback, auto_ack=False)
    print(f"消费启动｜初始QPS:{FLOW['curr_qps']} 最大QPS:{FLOW['max_qps']} 斜率可控")
    ch.start_consuming()

# ===================== 启动入口 =====================
if __name__ == '__main__':
    # 启动流控后台线程
    threading.Thread(target=flow_schedule, daemon=True).start()
    threading.Thread(target=reset_count, daemon=True).start()
    
    # 方式1: 模拟Client端峰值流量【生产端】- 按需执行
    # for i in range(100): producer({"msg": f"大模型请求{i}: 技术方案总结"})

    # 方式2: 启动消费端【填谷+控速+调用方舟】- 主运行
    consumer()
```



</Tab>
<Tab zoneid="wKWy1IEX3C" title="Go">
<TabTitle>Go</TabTitle>

```Go
package main

import (
  "bytes"
  "encoding/json"
  "flag"
  "fmt"
  "io"
  "log"
  "net/http"
  "os"
  "sync"
  "time"

  amqp "github.com/rabbitmq/amqp091-go"
)

// ===================== 全局配置 =====================
const (
  MQQueue    = "client_ark_queue"
  MQUrl      = "amqp://guest:guest@127.0.0.1:5672/"
  ArkModel   = "doubao-seed-2-1-pro-260628"
  ArkBaseUrl = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
)

var (
  // Get API Key: https://console.volcengine.com/ark/region:ark+cn-beijing/apikey
  ArkApiKey = os.Getenv("ARK_API_KEY")
  MockMode  = false
)

// FlowConfig 流控配置
type FlowConfig struct {
  CurrQPS  int
  MaxQPS   int
  Step     int
  Interval time.Duration
  Count    int
  mu       sync.Mutex
}

// 全局流控对象
var flow = &FlowConfig{
  CurrQPS:  5,
  MaxQPS:   30,
  Step:     2,
  Interval: 5 * time.Second,
  Count:    0,
}

// ===================== 1. 极简斜率可控流控【核心】=====================

// startFlowSchedule 后台协程：匀速增长消费速率，控制斜率
func startFlowSchedule() {
  ticker := time.NewTicker(flow.Interval)
  defer ticker.Stop()

  for range ticker.C {
    flow.mu.Lock()
    if flow.CurrQPS < flow.MaxQPS {
      flow.CurrQPS += flow.Step
      // 确保不超过最大值
      if flow.CurrQPS > flow.MaxQPS {
        flow.CurrQPS = flow.MaxQPS
      }
      log.Printf("QPS Limit Increased: Current=%d, Max=%d", flow.CurrQPS, flow.MaxQPS)
    }
    flow.mu.Unlock()
  }
}

// startResetCount 后台协程：每秒重置请求计数器，精准控QPS
func startResetCount() {
  ticker := time.NewTicker(1 * time.Second)
  defer ticker.Stop()

  for range ticker.C {
    flow.mu.Lock()
    flow.Count = 0
    flow.mu.Unlock()
  }
}

// allow 流控校验：是否允许发起本次请求
func allow() bool {
  flow.mu.Lock()
  defer flow.mu.Unlock()

  if flow.Count < flow.CurrQPS {
    flow.Count++
    return true
  }
  return false
}

// ===================== 3. 方舟API调用【大模型请求核心】=====================

type ArkRequest struct {
  Model    string    `json:"model"`
  Messages []Message `json:"messages"`
}

type Message struct {
  Role    string `json:"role"`
  Content string `json:"content"`
}

type ArkResponse struct {
  Choices []struct {
    Message Message `json:"message"`
  } `json:"choices"`
  Error *struct {
    Message string `json:"message"`
    Type    string `json:"type"`
  } `json:"error,omitempty"`
}

// callArk 调用方舟大模型API
func callArk(msg string) (string, error) {
  if MockMode {
    time.Sleep(50 * time.Millisecond) // 模拟网络延迟
    return "Mocked Response: " + msg, nil
  }

  reqBody := ArkRequest{
    Model: ArkModel,
    Messages: []Message{
      {Role: "user", Content: msg},
    },
  }

  jsonData, err := json.Marshal(reqBody)
  if err != nil {
    return "", err
  }

  req, err := http.NewRequest("POST", ArkBaseUrl, bytes.NewBuffer(jsonData))
  if err != nil {
    return "", err
  }

  req.Header.Set("Content-Type", "application/json")
  req.Header.Set("Authorization", "Bearer "+ArkApiKey)

  client := &http.Client{Timeout: 60 * time.Second}
  resp, err := client.Do(req)
  if err != nil {
    return "", err
  }
  defer resp.Body.Close()

  body, err := io.ReadAll(resp.Body)
  if err != nil {
    return "", err
  }

  if resp.StatusCode != http.StatusOK {
    return "", fmt.Errorf("API error: status=%d, body=%s", resp.StatusCode, string(body))
  }

  var arkResp ArkResponse
  if err := json.Unmarshal(body, &arkResp); err != nil {
    return "", err
  }

  if arkResp.Error != nil {
    return "", fmt.Errorf("API error: %s", arkResp.Error.Message)
  }

  if len(arkResp.Choices) > 0 {
    return arkResp.Choices[0].Message.Content, nil
  }
  return "", fmt.Errorf("empty choices in response")
}

// ===================== 4. MQ消费者【填谷+斜率控速+调用方舟，核心主逻辑】=====================

// startConsumer 消费端核心：削峰后的流量，斜率可控匀速消费，调用方舟大模型
func startConsumer() {
  conn, err := amqp.Dial(MQUrl)
  if err != nil {
    log.Fatalf("Failed to connect to RabbitMQ: %v", err)
  }
  defer conn.Close()

  ch, err := conn.Channel()
  if err != nil {
    log.Fatalf("Failed to open a channel: %v", err)
  }
  defer ch.Close()

  // 声明队列 (Durable=true)
  q, err := ch.QueueDeclare(
    MQQueue, // name
    true,    // durable
    false,   // delete when unused
    false,   // exclusive
    false,   // no-wait
    nil,     // arguments
  )
  if err != nil {
    log.Fatalf("Failed to declare a queue: %v", err)
  }

  // 设置QoS (PrefetchCount=1)
  err = ch.Qos(
    1,     // prefetch count
    0,     // prefetch size
    false, // global
  )
  if err != nil {
    log.Fatalf("Failed to set QoS: %v", err)
  }

  msgs, err := ch.Consume(
    q.Name, // queue
    "",     // consumer
    false,  // auto-ack (设置为false，手动ACK)
    false,  // exclusive
    false,  // no-local
    false,  // no-wait
    nil,    // args
  )
  if err != nil {
    log.Fatalf("Failed to register a consumer: %v", err)
  }

  log.Printf("消费启动｜初始QPS:%d 最大QPS:%d 斜率可控", flow.CurrQPS, flow.MaxQPS)

  forever := make(chan bool)

  go func() {
    for d := range msgs {
      // 解析消息
      var reqData map[string]string
      if err := json.Unmarshal(d.Body, &reqData); err != nil {
        log.Printf("Error parsing JSON: %v", err)
        d.Nack(false, false) // 无法解析，丢弃或放入死信队列
        continue
      }
      msgContent := reqData["msg"]

      // 流控校验
      if !allow() {
        // 不通过则消息重回队列
        d.Nack(false, true)
        // 稍微sleep一下避免空转太快
        time.Sleep(10 * time.Millisecond)
        continue
      }

      // 调用方舟大模型
      respContent, err := callArk(msgContent)
      if err != nil {
        log.Printf("调用方舟失败: %v", err)
        d.Nack(false, true) // 失败重试
      } else {
        // 打印日志 (截取部分长度)
        reqSnippet := msgContent
        if len(reqSnippet) > 15 {
          reqSnippet = reqSnippet[:15]
        }
        respSnippet := respContent
        if len(respSnippet) > 20 {
          respSnippet = respSnippet[:20]
        }
        log.Printf("请求:%s | 响应:%s", reqSnippet, respSnippet)


        // 消费成功手动ACK
        d.Ack(false)
      }
    }
  }()

  <-forever
}

// ===================== 2. MQ生产者【Client端请求投递，削峰】=====================

// startProducer 投递Client请求到MQ，无速率限制，承接峰值流量
func startProducer(count int) {
  conn, err := amqp.Dial(MQUrl)
  if err != nil {
    log.Fatalf("Failed to connect to RabbitMQ: %v", err)
  }
  defer conn.Close()

  ch, err := conn.Channel()
  if err != nil {
    log.Fatalf("Failed to open a channel: %v", err)
  }
  defer ch.Close()

  q, err := ch.QueueDeclare(
    MQQueue, // name
    true,    // durable
    false,   // delete when unused
    false,   // exclusive
    false,   // no-wait
    nil,     // arguments
  )
  if err != nil {
    log.Fatalf("Failed to declare a queue: %v", err)
  }

  log.Printf("开始投递 %d 条消息...", count)
  for i := 0; i < count; i++ {
    msgContent := fmt.Sprintf("大模型请求%d: 技术方案总结", i)
    reqData := map[string]string{"msg": msgContent}
    body, _ := json.Marshal(reqData)

    err = ch.Publish(
      "",     // exchange
      q.Name, // routing key
      false,  // mandatory
      false,  // immediate
      amqp.Publishing{
        DeliveryMode: amqp.Persistent,
        ContentType:  "application/json",
        Body:         body,
      })
    if err != nil {
      log.Fatalf("Failed to publish a message: %v", err)
    }
  }
  log.Printf("成功投递 %d 条消息", count)
}

// ===================== 启动入口 =====================

func main() {
  mode := flag.String("mode", "consumer", "运行模式: consumer | producer")
  count := flag.Int("count", 100, "生产者发送消息数量")
  mock := flag.Bool("mock", false, "是否开启Mock模式(不真实调用API)")
  flag.Parse()

  if *mock {
    MockMode = true
    log.Println("Mock模式已开启")
  }

  if *mode == "producer" {
    startProducer(*count)
    return
  }

  // 启动流控后台协程
  go startFlowSchedule()
  go startResetCount()

  // 启动消费端
  startConsumer()
}
```



</Tab>
</Tabs>



&nbsp;

<span id="56db1a74"></span>
## 实践 QPS 爬坡策略

客户端通过实时监测服务端响应状态，动态调整请求速率，逐步提升吞吐量，从而有效避免服务限流、确保服务稳定性。

<span id="ad1310f6"></span>
### 设计思路

QPS 爬坡工作原理如下图所示，统计固定时间间隔的限流错误，来评估线上服务负载。


1. 逐步提升请求发送速率（QPS）；

2. 当发现错误率提升时，按照策略降低或稳定 QPS；

3. 当服务稳定后继续提升QPS，并循环1、2；

4. 最终达到平台对应模型的总限流（TPM、RPM）。


<img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHhtbG5zOnhsaW5rPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hsaW5rIiB2ZXJzaW9uPSIxLjEiIHdpZHRoPSI3NTVweCIgaGVpZ2h0PSIxMDQ3cHgiIHZpZXdCb3g9Ii0wLjUgLTAuNSA3NTUgMTA0NyI+PGRlZnMvPjxnPjxwYXRoIGQ9Ik0gNjMyIDIwNyBMIDYzMiAyMzcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjYzMiIgY3k9IjIwNCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDYzMiAyNDIuODggTCA2MjguNSAyMzUuODggTCA2MzIgMjM3LjYzIEwgNjM1LjUgMjM1Ljg4IFoiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA2MzIgMzI3IEwgNjMyIDU3Ny42MyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJzdHJva2UiLz48ZWxsaXBzZSBjeD0iNjMyIiBjeT0iMzI0IiByeD0iMyIgcnk9IjMiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNjMyIDU4Mi44OCBMIDYyOC41IDU3NS44OCBMIDYzMiA1NzcuNjMgTCA2MzUuNSA1NzUuODggWiIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDYzMiAzMjcgTCA2MzIgMzQ0IEwgNDMyIDM0NCBMIDQzMiAzNTcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjYzMiIgY3k9IjMyNCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiAzNjIuODggTCA0MjguNSAzNTUuODggTCA0MzIgMzU3LjYzIEwgNDM1LjUgMzU1Ljg4IFoiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgNDA3IEwgNDMyIDQzNy42MyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJzdHJva2UiLz48ZWxsaXBzZSBjeD0iNDMyIiBjeT0iNDA0IiByeD0iMyIgcnk9IjMiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDMyIDQ0Mi44OCBMIDQyOC41IDQzNS44OCBMIDQzMiA0MzcuNjMgTCA0MzUuNSA0MzUuODggWiIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA1MjcgTCA0MzIgNTU3LjYzIiBmaWxsPSJub25lIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9InN0cm9rZSIvPjxlbGxpcHNlIGN4PSI0MzIiIGN5PSI1MjQiIHJ4PSIzIiByeT0iMyIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgNTYyLjg4IEwgNDI4LjUgNTU1Ljg4IEwgNDMyIDU1Ny42MyBMIDQzNS41IDU1NS44OCBaIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDMyIDUyNyBMIDQzMiA3NDQgTCA3MiA3NDQgTCA3MiA5NTcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjQzMiIgY3k9IjUyNCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDcyIDk2Mi44OCBMIDY4LjUgOTU1Ljg4IEwgNzIgOTU3LjYzIEwgNzUuNSA5NTUuODggWiIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA2NDQgTCA1NzIgNjA0IiBmaWxsPSJub25lIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9InN0cm9rZSIvPjxwYXRoIGQ9Ik0gNDMyIDY0NyBMIDQzMiA2NzcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjQzMiIgY3k9IjY0NCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA2ODIuODggTCA0MjguNSA2NzUuODggTCA0MzIgNjc3LjYzIEwgNDM1LjUgNjc1Ljg4IFoiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgNzI3IEwgNDMyIDc1Ny42MyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJzdHJva2UiLz48ZWxsaXBzZSBjeD0iNDMyIiBjeT0iNzI0IiByeD0iMyIgcnk9IjMiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDMyIDc2Mi44OCBMIDQyOC41IDc1NS44OCBMIDQzMiA3NTcuNjMgTCA0MzUuNSA3NTUuODggWiIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA4NDcgTCA0MzIgODc3LjYzIiBmaWxsPSJub25lIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9InN0cm9rZSIvPjxlbGxpcHNlIGN4PSI0MzIiIGN5PSI4NDQiIHJ4PSIzIiByeT0iMyIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgODgyLjg4IEwgNDI4LjUgODc1Ljg4IEwgNDMyIDg3Ny42MyBMIDQzNS41IDg3NS44OCBaIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDMyIDg0NyBMIDQzMiA4NjQgTCA1OTIgODY0IEwgNTkyIDg3Ny42MyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJzdHJva2UiLz48ZWxsaXBzZSBjeD0iNDMyIiBjeT0iODQ0IiByeD0iMyIgcnk9IjMiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNTkyIDg4Mi44OCBMIDU4OC41IDg3NS44OCBMIDU5MiA4NzcuNjMgTCA1OTUuNSA4NzUuODggWiIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBzdHJva2UtbWl0ZXJsaW1pdD0iMTAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA4NDcgTCA0MzIgODY0IEwgMjcyIDg2NCBMIDI3MiA4NzcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjQzMiIgY3k9Ijg0NCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDI3MiA4ODIuODggTCAyNjguNSA4NzUuODggTCAyNzIgODc3LjYzIEwgMjc1LjUgODc1Ljg4IFoiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSAyNzIgOTI3IEwgMjcyIDk0NCBMIDQzMiA5NDQgTCA0MzIgOTU3LjYzIiBmaWxsPSJub25lIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9InN0cm9rZSIvPjxlbGxpcHNlIGN4PSIyNzIiIGN5PSI5MjQiIHJ4PSIzIiByeT0iMyIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgOTYyLjg4IEwgNDI4LjUgOTU1Ljg4IEwgNDMyIDk1Ny42MyBMIDQzNS41IDk1NS44OCBaIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDMyIDkyNyBMIDQzMiA5NTcuNjMiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PGVsbGlwc2UgY3g9IjQzMiIgY3k9IjkyNCIgcng9IjMiIHJ5PSIzIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48cGF0aCBkPSJNIDQzMiA5NjIuODggTCA0MjguNSA5NTUuODggTCA0MzIgOTU3LjYzIEwgNDM1LjUgOTU1Ljg4IFoiIGZpbGw9IiMwMDAwMDAiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA1OTIgOTI3IEwgNTkyIDk0NCBMIDQzMiA5NDQgTCA0MzIgOTU3LjYzIiBmaWxsPSJub25lIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9InN0cm9rZSIvPjxlbGxpcHNlIGN4PSI1OTIiIGN5PSI5MjQiIHJ4PSIzIiByeT0iMyIgZmlsbD0iIzAwMDAwMCIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PHBhdGggZD0iTSA0MzIgOTYyLjg4IEwgNDI4LjUgOTU1Ljg4IEwgNDMyIDk1Ny42MyBMIDQzNS41IDk1NS44OCBaIiBmaWxsPSIjMDAwMDAwIiBzdHJva2U9IiMwMDAwMDAiIHN0cm9rZS1taXRlcmxpbWl0PSIxMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxwYXRoIGQ9Ik0gNDkyIDk4NCBMIDY5MiAyODQiIGZpbGw9Im5vbmUiIHN0cm9rZT0iIzAwMDAwMCIgc3Ryb2tlLW1pdGVybGltaXQ9IjEwIiBwb2ludGVyLWV2ZW50cz0ic3Ryb2tlIi8+PHJlY3QgeD0iMiIgeT0iMTU0IiB3aWR0aD0iNzUwIiBoZWlnaHQ9Ijg5MCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSJub25lIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogNzQ4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogNTk5cHg7IG1hcmdpbi1sZWZ0OiAzcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPjwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMTUyIiB5PSIyMjQiIHdpZHRoPSI1NjAiIGhlaWdodD0iNDMwIiBmaWxsPSIjRDVFOEQ0IiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiA1NThweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA0MzlweDsgbWFyZ2luLWxlZnQ6IDE1M3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj48L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjE1MiIgeT0iNjc0IiB3aWR0aD0iNTYwIiBoZWlnaHQ9IjM0MCIgZmlsbD0iI0Q1RThENCIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogNTU4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogODQ0cHg7IG1hcmdpbi1sZWZ0OiAxNTNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+PC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSI1NzIiIHk9IjE2NCIgd2lkdGg9IjEyMCIgaGVpZ2h0PSI0MCIgcng9IjIwIiByeT0iMjAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDExOHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDE4NHB4OyBtYXJnaW4tbGVmdDogNTczcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuWPkei1t+ivt+axgjwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iNTcyIiB5PSI1ODQiIHdpZHRoPSIxMjAiIGhlaWdodD0iNDAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDExOHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDYwNHB4OyBtYXJnaW4tbGVmdDogNTczcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuetieW+hemHjeivlTwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMjkxLjc1IiB5PSIyIiB3aWR0aD0iMCIgaGVpZ2h0PSIwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAwcHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogMnB4OyBtYXJnaW4tbGVmdDogMjkyLjc1cHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuS7pOeJjOS4jei2szwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMjkxLjgxIiB5PSIzIiB3aWR0aD0iMCIgaGVpZ2h0PSIwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAwcHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogM3B4OyBtYXJnaW4tbGVmdDogMjkyLjgxcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuiOt+WPluS7pOeJjDwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iNTcyIiB5PSIyNDQiIHdpZHRoPSIxMjAiIGhlaWdodD0iODAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDExOHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDI4NHB4OyBtYXJnaW4tbGVmdDogNTczcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuS7pOeJjOahtumZkOa1gTwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMzcyIiB5PSIzNjQiIHdpZHRoPSIxMjAiIGhlaWdodD0iNDAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDExOHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDM4NHB4OyBtYXJnaW4tbGVmdDogMzczcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuWPkemAgeivt+axgjwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMjkxLjgiIHk9IjMiIHdpZHRoPSIwIiBoZWlnaHQ9IjAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDBweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiAzcHg7IG1hcmdpbi1sZWZ0OiAyOTIuOHB4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7lpLHotKU8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjI5MS45IiB5PSI0IiB3aWR0aD0iMCIgaGVpZ2h0PSIwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAwcHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogNHB4OyBtYXJnaW4tbGVmdDogMjkyLjlweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+5q2j56GuPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIzNzIiIHk9IjQ0NCIgd2lkdGg9IjEyMCIgaGVpZ2h0PSI4MCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTE4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogNDg0cHg7IG1hcmdpbi1sZWZ0OiAzNzNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+5pyN5Yqh56uv5ZON5bqUPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIyOTEuNzUiIHk9IjUiIHdpZHRoPSIwIiBoZWlnaHQ9IjAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDBweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA1cHg7IG1hcmdpbi1sZWZ0OiAyOTIuNzVweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+5Y+v6YeN6K+VPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIyOTIuMTMiIHk9IjMiIHdpZHRoPSIwIiBoZWlnaHQ9IjAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDBweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiAzcHg7IG1hcmdpbi1sZWZ0OiAyOTMuMTNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+6ZSZ6K+v57G75Z6LPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIzNzIiIHk9IjU2NCIgd2lkdGg9IjEyMCIgaGVpZ2h0PSI4MCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTE4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogNjA0cHg7IG1hcmdpbi1sZWZ0OiAzNzNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+6K6w5b2V6ZSZ6K+vPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIxMiIgeT0iOTY0IiB3aWR0aD0iMTIwIiBoZWlnaHQ9IjQwIiByeD0iMjAiIHJ5PSIyMCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTE4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogOTg0cHg7IG1hcmdpbi1sZWZ0OiAxM3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7ov5Tlm57nu5Pmnpw8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjM3MiIgeT0iNjg0IiB3aWR0aD0iMTIwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAxMThweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA3MDRweDsgbWFyZ2luLWxlZnQ6IDM3M3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7orqHnrpfplJnor6/njoc8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjI5MS43NSIgeT0iMyIgd2lkdGg9IjAiIGhlaWdodD0iMCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDNweDsgbWFyZ2luLWxlZnQ6IDI5Mi43NXB4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7kvY7plJnor6/njoc8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjI5Mi42OSIgeT0iMyIgd2lkdGg9IjAiIGhlaWdodD0iMCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDNweDsgbWFyZ2luLWxlZnQ6IDI5My42OXB4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7pm7bplJnor688L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjI5Mi43IiB5PSIyIiB3aWR0aD0iMCIgaGVpZ2h0PSIwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAwcHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogMnB4OyBtYXJnaW4tbGVmdDogMjkzLjdweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+6auY6ZSZ6K+v546HPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIzNzIiIHk9Ijc2NCIgd2lkdGg9IjEyMCIgaGVpZ2h0PSI4MCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTE4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogODA0cHg7IG1hcmdpbi1sZWZ0OiAzNzNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+6LCD5pW0562W55WlPC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIyMTIiIHk9Ijg4NCIgd2lkdGg9IjEyMCIgaGVpZ2h0PSI0MCIgZmlsbD0iI2ZmZmZmZiIgc3Ryb2tlPSIjMDAwMDAwIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTE4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogOTA0cHg7IG1hcmdpbi1sZWZ0OiAyMTNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+6ZmN5L2OIFFQUzwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PHJlY3QgeD0iMzcyIiB5PSI4ODQiIHdpZHRoPSIxMjAiIGhlaWdodD0iNDAiIGZpbGw9IiNmZmZmZmYiIHN0cm9rZT0iIzAwMDAwMCIgcG9pbnRlci1ldmVudHM9ImFsbCIvPjxnIHRyYW5zZm9ybT0idHJhbnNsYXRlKC0wLjUgLTAuNSkiPjxmb3JlaWduT2JqZWN0IHN0eWxlPSJvdmVyZmxvdzogdmlzaWJsZTsgdGV4dC1hbGlnbjogbGVmdDsiIHBvaW50ZXItZXZlbnRzPSJub25lIiB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIj48ZGl2IHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5L3hodG1sIiBzdHlsZT0iZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IHVuc2FmZSBjZW50ZXI7IGp1c3RpZnktY29udGVudDogdW5zYWZlIGNlbnRlcjsgd2lkdGg6IDExOHB4OyBoZWlnaHQ6IDFweDsgcGFkZGluZy10b3A6IDkwNHB4OyBtYXJnaW4tbGVmdDogMzczcHg7Ij48ZGl2IHN0eWxlPSJib3gtc2l6aW5nOiBib3JkZXItYm94OyBmb250LXNpemU6IDA7IHRleHQtYWxpZ246IGNlbnRlcjsgIj48ZGl2IHN0eWxlPSJkaXNwbGF5OiBpbmxpbmUtYmxvY2s7IGZvbnQtc2l6ZTogMTNweDsgZm9udC1mYW1pbHk6IEhlbHZldGljYTsgY29sb3I6ICMwMDAwMDA7IGxpbmUtaGVpZ2h0OiAxLjI7IHBvaW50ZXItZXZlbnRzOiBhbGw7IHdoaXRlLXNwYWNlOiBub3JtYWw7IHdvcmQtd3JhcDogbm9ybWFsOyAiPuaPkOWNhyBRUFM8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjUzMiIgeT0iODg0IiB3aWR0aD0iMTIwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAxMThweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA5MDRweDsgbWFyZ2luLWxlZnQ6IDUzM3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7lv6vpgJ/mj5DljYc8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjM3MiIgeT0iOTY0IiB3aWR0aD0iMTIwIiBoZWlnaHQ9IjQwIiBmaWxsPSIjZmZmZmZmIiBzdHJva2U9IiMwMDAwMDAiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAxMThweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA5ODRweDsgbWFyZ2luLWxlZnQ6IDM3M3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj7mm7TmlrDpmZDmtYHlmag8L2Rpdj48L2Rpdj48L2Rpdj48L2ZvcmVpZ25PYmplY3Q+PC9nPjxyZWN0IHg9IjE3MiIgeT0iNjk0IiB3aWR0aD0iMTQwIiBoZWlnaHQ9IjIwIiBmaWxsPSJub25lIiBzdHJva2U9Im5vbmUiIHBvaW50ZXItZXZlbnRzPSJhbGwiLz48ZyB0cmFuc2Zvcm09InRyYW5zbGF0ZSgtMC41IC0wLjUpIj48Zm9yZWlnbk9iamVjdCBzdHlsZT0ib3ZlcmZsb3c6IHZpc2libGU7IHRleHQtYWxpZ246IGxlZnQ7IiBwb2ludGVyLWV2ZW50cz0ibm9uZSIgd2lkdGg9IjEwMCUiIGhlaWdodD0iMTAwJSI+PGRpdiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94aHRtbCIgc3R5bGU9ImRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiB1bnNhZmUgY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHVuc2FmZSBjZW50ZXI7IHdpZHRoOiAxMzhweDsgaGVpZ2h0OiAxcHg7IHBhZGRpbmctdG9wOiA3MDRweDsgbWFyZ2luLWxlZnQ6IDE3M3B4OyI+PGRpdiBzdHlsZT0iYm94LXNpemluZzogYm9yZGVyLWJveDsgZm9udC1zaXplOiAwOyB0ZXh0LWFsaWduOiBjZW50ZXI7ICI+PGRpdiBzdHlsZT0iZGlzcGxheTogaW5saW5lLWJsb2NrOyBmb250LXNpemU6IDEzcHg7IGZvbnQtZmFtaWx5OiBIZWx2ZXRpY2E7IGNvbG9yOiAjMDAwMDAwOyBsaW5lLWhlaWdodDogMS4yOyBwb2ludGVyLWV2ZW50czogYWxsOyB3aGl0ZS1zcGFjZTogbm9ybWFsOyB3b3JkLXdyYXA6IG5vcm1hbDsgIj5RUFMg5Yqo5oCB6LCD5pW0PC9kaXY+PC9kaXY+PC9kaXY+PC9mb3JlaWduT2JqZWN0PjwvZz48cmVjdCB4PSIxNzIiIHk9IjIzNCIgd2lkdGg9IjE0MCIgaGVpZ2h0PSIyMCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJub25lIiBwb2ludGVyLWV2ZW50cz0iYWxsIi8+PGcgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoLTAuNSAtMC41KSI+PGZvcmVpZ25PYmplY3Qgc3R5bGU9Im92ZXJmbG93OiB2aXNpYmxlOyB0ZXh0LWFsaWduOiBsZWZ0OyIgcG9pbnRlci1ldmVudHM9Im5vbmUiIHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiPjxkaXYgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkveGh0bWwiIHN0eWxlPSJkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogdW5zYWZlIGNlbnRlcjsganVzdGlmeS1jb250ZW50OiB1bnNhZmUgY2VudGVyOyB3aWR0aDogMTM4cHg7IGhlaWdodDogMXB4OyBwYWRkaW5nLXRvcDogMjQ0cHg7IG1hcmdpbi1sZWZ0OiAxNzNweDsiPjxkaXYgc3R5bGU9ImJveC1zaXppbmc6IGJvcmRlci1ib3g7IGZvbnQtc2l6ZTogMDsgdGV4dC1hbGlnbjogY2VudGVyOyAiPjxkaXYgc3R5bGU9ImRpc3BsYXk6IGlubGluZS1ibG9jazsgZm9udC1zaXplOiAxM3B4OyBmb250LWZhbWlseTogSGVsdmV0aWNhOyBjb2xvcjogIzAwMDAwMDsgbGluZS1oZWlnaHQ6IDEuMjsgcG9pbnRlci1ldmVudHM6IGFsbDsgd2hpdGUtc3BhY2U6IG5vcm1hbDsgd29yZC13cmFwOiBub3JtYWw7ICI+UVBTIOeIrOWdoeaguOW/g+a1geeoizwvZGl2PjwvZGl2PjwvZGl2PjwvZm9yZWlnbk9iamVjdD48L2c+PC9nPjwvc3ZnPg==" />

<span id="446e099a"></span>
### 核心机制1：动态调整速率

QPS Climber （每秒查询率爬坡器）采用"试错\-调整"策略，通过周期性评估请求成功率，动态调整请求速率。核心实现在 `adjustQPS()` 方法中。


示例代码

```Go
func (q *QPSClimber) adjustQPS() {
    // 计算请求总数与错误率
    acceptCount := float64(q.counter.Count(Accept))
    serverOverloadedCount := float64(q.counter.Count(ServerOverloadedCode))
    unknownCount := float64(q.counter.Count(UnknownCode))
    errorAll := serverOverloadedCount + unknownCount
    errorRatio := errorAll / acceptCount
    
    // 根据错误率动态调整QPS
    oldRate, newRate := float64(q.limiter.Limit()), float64(0)
    switch {
    case errorRatio >= q.options.StrictErrorRatio:
        // 高错误率场景：降低请求速率
        newRate = oldRate - oldRate*q.options.ProbeRatio
    case errorRatio >= q.options.RelaxErrorRatio:
        // 中等错误率场景：维持当前请求速率
        newRate = oldRate
    case errorRatio > 0:
        // 低错误率场景：小幅提升请求速率进行探测
        newRate = oldRate + oldRate*q.options.ProbeRatio
    case errorRatio == 0:
        // 零错误场景：更积极地提升请求速率
        newRate = oldRate + oldRate*q.options.FastProbeRatio
        
        // 防止请求量不足时速率无限增长
        if acceptCount*1.5 < oldRate*q.options.AdjustInterval.Seconds() {
            newRate = oldRate
        }
    }
    
    // 应用速率调整并设置边界限制
    finalRate := minMax(1, float64(q.options.MaxRate), newRate)
    if finalRate != oldRate {
        q.limiter.SetLimit(rate.Limit(finalRate))
        q.limiter.SetBurst(int(finalRate))
    }
}
```



&nbsp;

<span id="02ac6900"></span>
### 核心机制2：客户端限流与重试策略

QPS Climber 实现了两层保护机制：


1. **客户端令牌桶限流**：通过 `golang.org/x/time/rate` 包实现令牌桶算法，确保请求不会超过设定的QPS上限

2. **指数退避重试**：对失败请求采用指数退避策略进行重试，避免短时间内反复冲击服务端



示例代码

核心实现在 `DoRequest()` 方法中：

```Go
func (q *QPSClimber) DoRequest(ctx context.Context, req *model.CreateChatCompletionRequest) (model.ChatCompletionResponse, error) {
    // 初始化指数退避器
    backOff := newExponentialBackoff(q.options.RetryBaseDelay, q.options.RetryMaxDelay)
    
    for {
        select {
        case <-ctx.Done():
            return model.ChatCompletionResponse{}, ctx.Err()
        default:
        }
        
        // 客户端令牌桶限流
        if !q.limiter.Allow() {
            backOff.wait()
            continue
        }
        
        // 记录已接受的请求并执行
        q.Record(Accept)
        resp, err := q.client.CreateChatCompletion(ctx, req)
        if err == nil {
            return resp, nil
        }
        
        // 错误处理与重试决策
        statusCode, retry := needRetryError(err)
        q.Record(convertToCode(statusCode))
        
        if !retry {
            return resp, err
        }
        
        // 指数退避等待
        backOff.wait()
    }
}
```



&nbsp;

<span id="18017861"></span>
### 核心机制3：错误分类后智能路由

将服务端响应错误分为下面几类：


* `ServerOverloadedCode`：服务过载（如HTTP 429）

* `InternalServerError`：服务器内部错误（如HTTP 500）

* `UnknownCode`：其他请求错误（如 HTTP 400）


通过 `convertToCode()` 方法实现错误智能分类，为动态速率调整提供决策依据：


示例代码

```Go
func convertToCode(statusCode int) Code {
  switch {
  case statusCode >= http.StatusInternalServerError:
    return InternalServerError
  case statusCode == http.StatusTooManyRequests:
    return ServerOverloadedCode
  case statusCode == http.StatusOK:
    return SuccessCode
  default:
    return UnknownCode
  }
}
```



&nbsp;

<span id="308e9edd"></span>
### 代码配置


配置示例

```Go
func defaultOptions() *Options {
  return &Options{
    AdjustInterval:   10 * time.Second,
    InitialRate:      10,
    MaxRate:          1000,
    StrictErrorRatio: 0.05,
    RelaxErrorRatio:  0.01,
    ProbeRatio:       0.05,
    FastProbeRatio:   0.1,
    RetryBaseDelay: 100 * time.Millisecond,
    RetryMaxDelay:  3 * time.Second,
  }
}
```



&nbsp;

参数说明


|参数名 |默认值 |推荐值范围 |调优建议 |
|---|---|---|---|
|**InitialRate** |10 |5\-50 |根据服务初始承载能力设置，新服务建议从低值开始 |
|**MaxRate** |1000 |需根据服务配额估算 |可根据业务请求使用量（TPM）和请求频率（RPM）来估算，建议设置为服务额定QPS的80%\-90%，留有余量。 |
|**AdjustInterval** |10s |5\-15s |流量波动大时可适当缩短间隔。 |
|**StrictErrorRatio** |0.05 |0.03\-0.1 |错误率阈值1，错误率高于该阈值，会降低请求频率。<br><br>对稳定性要求高时可降低该值。 |
|**RelaxErrorRatio** |0.01 |0.005\-0.05 |允许少量错误时可适当提高该值。 |
|**ProbeRatio** |0.05 |0.03\-0.1 |速率调整步长，波动大时可降低步长。 |
|**RetryBaseDelay** |100 ms |50ms\-500ms |单位 ms，初始重试延迟，根据服务响应速度调整。 |
|**RetryMaxDelay** |3 s |3s\-10s |最大重试等待时间。 |


<span id="be8f89ed"></span>
### 使用建议


* **单例模式使用**：在应用中创建单一的 `QPSClimber` 实例，所有API调用共享该实例，避免资源浪费。

* **统一错误处理**：通过 `needRetryError()` 方法统一处理各类错误，确保重试决策一致性。

* **并发请求控制**：结合Go语言的 `sync.WaitGroup` 实现高效并发请求，同时通过QPS Climber控制总体速率。


```Go
// 请求总量
var total atomic.Int64
total.Store(100000)
// 并发请求示例
var wg sync.WaitGroup
concurrency := 1000
wg.Add(concurrency)

for i := 0; i < concurrency; i++ {
    go func() {
        defer wg.Done()
        for total.Add(-1) >= 0 {
            // 业务请求代码
            req := &model.CreateChatCompletionRequest{...}
            _, err := qpsClimber.DoRequest(ctx, req)
            // 错误处理
        }
    }()
}
wg.Wait()
```



* **预热机制**：应用启动时设置较低的初始QPS，通过 `adjustInterval` 逐步提升，避免冷启动时的流量冲击，导致被熔断。

* **自适应调整**：利用QPS Climber的动态调整能力，让系统自动适应流量变化。

* **监控告警**：关注QPS调整日志，设置错误率、成功率等关键指标的监控告警。

* **降级预案**：在极端情况下，考虑实现请求降级或熔断机制，确保核心功能可用。


<span id="5f09a5c5"></span>
### 完整项目代码


* Go


<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/55c4a0b30f824c7e85da1126a7dfb87b~tplv-goo7wpa0wc-image.image" name="chat-request-climber.zip">chat-request-climber.zip</Attachment>



* Python


<Attachment link="https://p9-arcosite.byteimg.com/tos-cn-i-goo7wpa0wc/560639dc068d4ebb8274a4dbd80ef85d~tplv-goo7wpa0wc-image.image" name="python_example.zip">python_example.zip</Attachment>


<span id="27d03c9d"></span>
## 实践 退避重试策略

使用退避算法进行请求重试，是避免限流的简单且有效方法（不仅仅在突发流量场景），其中随机指数退避算法实现自动重试请求。

<span id="e6eaf2db"></span>
### 核心设计思路

当遇到速率限制错误时，先进行短暂休眠，随后重新发起未成功的请求。若请求依旧失败，系统会增加休眠时长，再次尝试，该过程会持续进行，直至请求成功或达到最大重试次数。

具备如下优势：


* 自动重试功能可使系统从速率限制错误中恢复，避免崩溃和数据丢失。

* 指数退避特性能快速进行首次重试。若前几次重试失败，较长的延迟时间可减少速率限制的触发。

* 在等待时间中加入随机抖动，避免大量请求同时重试。


<div data-tips="true" data-tips-type="warning" data-tips-is-title="true">注意</div>


<div data-tips="true" data-tips-type="warning">不成功的请求会计入每分钟的请求限制内，因此高频重试会更快达到限流阈值，导致更多请求失败。采用指数退避算法进行重试，能在遵守速率限制规则的前提下，提高请求成功的概率，保障系统的稳定运行。</div>


<span id="38b294ec"></span>
### 示例代码


示例代码

Tenacity 是一个第三方 Python 库，可用于简化重试的实现。下面示例是如何为一个请求增加随机指数退避。

```Python
import os
# 升级方舟 SDK 到最新版本 pip install -U 'volcengine-python-sdk[ark]'
from volcenginesdkarkruntime import Ark
# 引入指数退避（exponential backoff）算法包
from tenacity import retry, stop_after_attempt, wait_random_exponential

client = Ark(
    # 从环境变量中读取您的方舟API Key
    api_key=os.environ.get("ARK_API_KEY"),
)

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def completion_with_backoff(**kwargs):
    return client.chat.completions.create(**kwargs)

resp = completion_with_backoff(
    model="doubao-seed-2-1-pro-260628", messages=[{"role": "user", "content": "hello"}]
)

print(resp.choices[0].message.content)
```



&nbsp;

<span id="9cdd0ce6"></span>
## 实践 使用TPM保障包

在可预测或者重点保障的业务，为了应对流量突增，可考虑购买 TPM 保障包来覆盖突发流量，方舟允许 TPM 保障包额度内的突发流量，提供更高的 SLA 和资源优先级。用户无需变更任何代码，只需在指定的接入点上购买 TPM 保障包即可。详细介绍及购买指引见 [在线推理（TPM 保障包）](https://www.volcengine.com/docs/82379/1510762) 。




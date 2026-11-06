package com.example.aw.collect.controller;

import com.example.aw.collect.mapper.CollectTaskMapper;
import com.example.aw.collect.service.CollectSubmitService;
import com.example.aw.collect.service.TaskEndService;
import com.example.aw.collect.service.TaskFinalAnswerQueryService;
import com.example.aw.collect.service.TaskStepDataQueryService;
import com.example.aw.collect.service.TaskStepToolsQueryService;
import com.example.aw.collect.service.TaskTreeQueryService;
import com.example.aw.collect.service.ThoughtQueryService;
import com.example.aw.collect.stream.ThoughtStreamHub;
import com.example.aw.gateway.HermesGatewayClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * hermes-hq 写报 REST API。
 * <p>
 * 主路径：新建会话 → collect/start 下发 → tree/stream 轮询 → nodes/data/final-answer 详情；
 * 历史见 {@code /api/history/*}。
 */
@RestController
@RequestMapping("/api")
public class CollectApiController {

    @Autowired
    private HermesGatewayClient hermesGatewayClient;

    @Autowired
    private CollectSubmitService collectSubmitService;

    @Autowired
    private TaskTreeQueryService taskTreeQueryService;

    @Autowired
    private TaskStepDataQueryService taskStepDataQueryService;

    @Autowired
    private TaskStepToolsQueryService taskStepToolsQueryService;

    @Autowired
    private TaskFinalAnswerQueryService taskFinalAnswerQueryService;

    @Autowired
    private ThoughtQueryService thoughtQueryService;

    @Autowired
    private CollectTaskMapper collectTaskMapper;

    @Autowired
    private ThoughtStreamHub thoughtStreamHub;

    @Autowired
    private TaskEndService taskEndService;

    /**
     * 新对话：向 Hermes 申请 session_id（可选；collect/start 无 session 时也会自动建）。
     */
    @PostMapping("/conversations")
    public ResponseEntity<Map<String, Object>> createConversation() {
        try {
            String sessionId = hermesGatewayClient.createSession();
            Map<String, Object> body = new LinkedHashMap<String, Object>();
            body.put("sessionId", sessionId);
            return ResponseEntity.status(HttpStatus.CREATED).body(body);
        } catch (Exception e) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", "gateway_create_session_failed");
            err.put("detail", e.getMessage());
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body(err);
        }
    }

    /**
     * 【前端主入口】用户发话下任务：无 sessionId 则自动创建会话。
     * 额外字段 payload（或 payloadJson / extra）原样写入 hermes_user_dialogues.payload_json。
     */
    @PostMapping("/collect/start")
    public ResponseEntity<Map<String, Object>> collectStart(@RequestBody Map<String, Object> req) {
        String sessionId = firstNonBlank(req, "sessionId", "session_id");
        String message = firstNonBlank(req, "message", "input");
        String taskId = firstNonBlank(req, "taskId", "task_id");

        if (message.isEmpty()) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", "message_required");
            return ResponseEntity.badRequest().body(err);
        }
        String taskType = firstNonBlank(req, "taskType", "task_type");
        if (taskType.isEmpty()) {
            // hermes-hq 仅保留写报；缺省按 report
            taskType = "report";
        }
        String payloadJson = CollectSubmitService.toPayloadJson(req);
        try {
            Map<String, Object> body = collectSubmitService.submitCollectStart(
                    sessionId.isEmpty() ? null : sessionId,
                    taskId.isEmpty() ? null : taskId,
                    message,
                    taskType,
                    payloadJson);
            return ResponseEntity.status(HttpStatus.ACCEPTED).body(body);
        } catch (IllegalStateException e) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.CONFLICT).body(err);
        } catch (IllegalArgumentException e) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", e.getMessage());
            return ResponseEntity.badRequest().body(err);
        } catch (Exception e) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", "collect_submit_failed");
            err.put("detail", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(err);
        }
    }

    /**
     * 任务概要。
     */
    @GetMapping("/tasks/{taskId}")
    public ResponseEntity<Map<String, Object>> getTask(@PathVariable String taskId) {
        Map<String, Object> task = collectTaskMapper.selectTaskById(taskId);
        if (task == null || task.isEmpty()) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", "task_not_found");
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(err);
        }
        Map<String, Object> body = new LinkedHashMap<String, Object>();
        body.put("taskId", task.get("task_id"));
        body.put("taskType", task.get("task_type"));
        body.put("sessionId", task.get("session_id"));
        body.put("status", task.get("status"));
        body.put("currentPhase", task.get("current_phase"));
        body.put("crossPlatform", task.get("cross_platform"));
        body.put("startedAt", task.get("started_at"));
        body.put("finishedAt", task.get("finished_at"));
        body.put("treeUrl", "/api/tasks/" + taskId + "/tree");
        body.put("thoughtsUrl", "/api/tasks/" + taskId + "/thoughts");
        body.put("thoughtsStreamUrl", "/api/tasks/" + taskId + "/thoughts/stream");
        return ResponseEntity.ok(body);
    }

    /**
     * 用户结束任务：pending/running → cancelled；步骤树不动。
     */
    @PostMapping("/tasks/{taskId}/end")
    public ResponseEntity<?> endTask(@PathVariable String taskId) {
        try {
            return ResponseEntity.ok(taskEndService.endTask(taskId));
        } catch (ResponseStatusException e) {
            HttpStatus status = e.getStatus();
            String reason = e.getReason() == null ? status.getReasonPhrase() : e.getReason();
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", reason);
            err.put("detail", reason);
            return ResponseEntity.status(status).body(err);
        } catch (Exception e) {
            Map<String, Object> err = new LinkedHashMap<String, Object>();
            err.put("error", "end_task_failed");
            err.put("detail", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(err);
        }
    }

    /**
     * 思考过程查询：完成态返回终稿；进行中 mode=live。
     */
    @GetMapping("/tasks/{taskId}/thoughts")
    public ResponseEntity<Map<String, Object>> getThoughts(@PathVariable String taskId) {
        Map<String, Object> body = thoughtQueryService.getThoughts(taskId);
        if (body.containsKey("error") && "task_not_found".equals(body.get("error"))) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
        }
        return ResponseEntity.ok(body);
    }

    /**
     * 思考流可回放时间线：tool.progress + toolName=_thinking。
     */
    @GetMapping("/tasks/{taskId}/thoughts/timeline")
    public ResponseEntity<Map<String, Object>> getThoughtsTimeline(
            @PathVariable String taskId,
            @RequestParam(value = "afterSeq", defaultValue = "0") long afterSeq) {
        Map<String, Object> body = thoughtQueryService.getTimeline(taskId, afterSeq);
        if (body.containsKey("error") && "task_not_found".equals(body.get("error"))) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(body);
        }
        return ResponseEntity.ok(body);
    }

    /**
     * 模型思考过程 SSE 中继。
     */
    @GetMapping(value = "/tasks/{taskId}/thoughts/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter thoughtStream(
            @PathVariable String taskId,
            @RequestParam(value = "afterSeq", required = false, defaultValue = "0") long afterSeq) {
        Map<String, Object> task = collectTaskMapper.selectTaskById(taskId);
        if (task == null || task.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "task_not_found");
        }
        return thoughtStreamHub.subscribe(taskId, ThoughtStreamHub.DEFAULT_TIMEOUT_MS, afterSeq);
    }

    /**
     * 步骤树（前端主轮询）。
     */
    @GetMapping("/tasks/{taskId}/tree")
    public ResponseEntity<Map<String, Object>> getTaskTree(@PathVariable String taskId) {
        Map<String, Object> tree = taskTreeQueryService.buildTaskTree(taskId);
        if (tree.containsKey("error") && "task_not_found".equals(tree.get("error"))) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(tree);
        }
        return ResponseEntity.ok(tree);
    }

    /**
     * 某步骤业务展示数据。
     */
    @GetMapping("/tasks/{taskId}/steps/{stepKey}/data")
    public ResponseEntity<Map<String, Object>> getStepData(
            @PathVariable String taskId,
            @PathVariable String stepKey) {
        Map<String, Object> data = taskStepDataQueryService.getStepData(taskId, stepKey);
        if (data.containsKey("error")) {
            String err = String.valueOf(data.get("error"));
            if ("task_not_found".equals(err) || "step_not_found".equals(err)) {
                return ResponseEntity.status(HttpStatus.NOT_FOUND).body(data);
            }
        }
        return ResponseEntity.ok(data);
    }

    /**
     * 某步骤下成功的工具调用列表。
     */
    @GetMapping("/tasks/{taskId}/steps/{stepKey}/tools")
    public ResponseEntity<Map<String, Object>> getStepTools(
            @PathVariable String taskId,
            @PathVariable String stepKey) {
        Map<String, Object> data = taskStepToolsQueryService.listSuccessTools(taskId, stepKey);
        if (data.containsKey("error") && "task_not_found".equals(data.get("error"))) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(data);
        }
        return ResponseEntity.ok(data);
    }

    /**
     * 模型最终回答全文。
     */
    @GetMapping("/tasks/{taskId}/final-answer")
    public ResponseEntity<Map<String, Object>> getFinalAnswer(@PathVariable String taskId) {
        Map<String, Object> answer = taskFinalAnswerQueryService.getFinalAnswer(taskId);
        if (answer.containsKey("error") && "task_not_found".equals(answer.get("error"))) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(answer);
        }
        return ResponseEntity.ok(answer);
    }

    /**
     * 单个节点详情。
     */
    @GetMapping("/tasks/{taskId}/nodes/{nodeId}")
    public ResponseEntity<Map<String, Object>> getNodeDetail(
            @PathVariable String taskId,
            @PathVariable String nodeId) {
        Map<String, Object> detail = taskTreeQueryService.getNodeDetail(taskId, nodeId);
        if (detail.containsKey("error")) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body(detail);
        }
        return ResponseEntity.ok(detail);
    }

    private String firstNonBlank(Map<String, Object> req, String key1, String key2) {
        Object v1 = req.get(key1);
        if (v1 != null && String.valueOf(v1).trim().length() > 0) {
            return String.valueOf(v1).trim();
        }
        Object v2 = req.get(key2);
        if (v2 != null && String.valueOf(v2).trim().length() > 0) {
            return String.valueOf(v2).trim();
        }
        return "";
    }
}

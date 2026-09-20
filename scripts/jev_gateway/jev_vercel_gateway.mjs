#!/usr/bin/env node
/**
 * Bridge the repository's legacy Jev response shape to Vercel AI Gateway.
 *
 * Input and output are JSON on stdin/stdout.  Keeping the gateway SDK here
 * means Python callers never handle an AI Gateway token or provider endpoint.
 */
import { experimental_evaluate as evaluate } from "ai";
import { gateway } from "@ai-sdk/gateway";

const readInput = async () => {
  let body = "";
  for await (const chunk of process.stdin) body += chunk;
  if (body.length > 2_000_000) throw new Error("Jev payload exceeds bridge input limit");
  const payload = JSON.parse(body);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("Jev payload must be an object");
  if (!payload.questions || typeof payload.questions !== "object" || Array.isArray(payload.questions)) throw new Error("Jev payload requires questions");
  return payload;
};

const questionsForGateway = questions => Object.fromEntries(Object.entries(questions).map(([id, question]) => {
  if (!question || typeof question !== "object" || Array.isArray(question)) throw new Error(`Question ${id} must be an object`);
  return [id, question.type === "noul" ? { ...question, type: "boolean" } : question];
}));

const headerValue = (headers, name) => {
  if (!headers) return undefined;
  if (typeof headers.get === "function") return headers.get(name) || headers.get(name.toLowerCase());
  if (typeof headers === "object") return headers[name] || headers[name.toLowerCase()];
  return undefined;
};

const retryAfterSeconds = value => {
  if (typeof value !== "string" && typeof value !== "number") return undefined;
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric >= 0) return numeric;
  const date = Date.parse(String(value));
  return Number.isFinite(date) ? Math.max(0, Math.ceil((date - Date.now()) / 1000)) : undefined;
};

const safeErrorReceipt = error => {
  const statusCandidate = error?.status ?? error?.statusCode ?? error?.response?.status;
  const status = Number.isInteger(statusCandidate) ? statusCandidate : undefined;
  const retryAfter = retryAfterSeconds(
    headerValue(error?.responseHeaders ?? error?.headers ?? error?.response?.headers, "retry-after"),
  );
  const rawMessage = error instanceof Error ? error.message : "";
  const kind = /timeout|timed out|abort/i.test(rawMessage) ? "timeout" : "gateway";
  // Never persist SDK error text: it may contain request state or provider bodies.
  const message = kind === "timeout" ? "Vercel AI Gateway request timed out" : "Vercel AI Gateway request failed";
  return {
    message: String(message).slice(0, 300),
    ...(status === undefined ? {} : { status }),
    ...(retryAfter === undefined ? {} : { retry_after_seconds: retryAfter }),
    kind,
  };
};

const legacyAnswers = (answers, providerMetadata) => {
  const confidence = providerMetadata?.typesafe?.confidence || {};
  return Object.fromEntries(Object.entries(answers).map(([id, answer]) => {
    const base = confidence[id] == null ? {} : { confidence: confidence[id] };
    if (answer.type === "boolean") return [id, { type: "noul", noul: answer.probability, ...base }];
    if (answer.type === "choice") return [id, { type: "choice", choice: answer.choice, probabilities: answer.probabilities, ...base }];
    if (answer.type === "score") return [id, { type: "score", score: answer.score, probabilities: answer.probabilities, ...base }];
    throw new Error(`Unsupported Jev answer type for ${id}`);
  }));
};

try {
  if (!process.env.AI_GATEWAY_API_KEY) throw new Error("AI_GATEWAY_API_KEY is not set");
  const payload = await readInput();
  const result = await evaluate({
    model: gateway.evaluationModel("typesafe-ai/jev"),
    state: payload.state,
    questions: questionsForGateway(payload.questions),
    // Python owns the bounded retry policy and its persisted attempt receipts.
    maxRetries: 0,
  });
  const routing = result.providerMetadata?.gateway?.routing;
  process.stdout.write(JSON.stringify({
    model: result.response?.modelId || "typesafe-ai/jev",
    answers: legacyAnswers(result.answers, result.providerMetadata),
    usage: {
      input_tokens: result.usage?.inputTokens,
      output_tokens: result.usage?.outputTokens,
    },
    _meta: {
      transport: "vercel-ai-gateway",
      generation_id: result.providerMetadata?.gateway?.generationId,
      provider: routing?.finalProvider,
    },
  }));
} catch (error) {
  // Do not echo a request body: it can contain the page text being evaluated.
  process.stderr.write(`Jev Vercel gateway error: ${JSON.stringify(safeErrorReceipt(error))}\n`);
  process.exitCode = 1;
}

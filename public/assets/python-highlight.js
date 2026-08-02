const pythonTokens = /(#.*$)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b(?:False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b)|(@[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)|(\b(?:str|int|float|bool|bytes|list|dict|tuple|set|object|Callable|Literal|TypedDict|BaseModel|StateGraph|Command|Runtime|AgentContext|WorkerState|AxiomCartState|RoutingDecision|AgentResult|HumanMessage|AIMessage|SystemMessage)\b)|(\b[A-Za-z_]\w*(?=\s*\())|(\b\d+(?:_\d+)*(?:\.\d+)?\b)|(\b[A-Z][A-Z0-9_]{2,}\b)/gm;

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

export function highlightPython(source) {
  let cursor = 0;
  let highlighted = "";
  for (const match of source.matchAll(pythonTokens)) {
    highlighted += escapeHtml(source.slice(cursor, match.index));
    const tokenClass = match[1]
      ? "token-comment"
      : match[2]
        ? "token-string"
        : match[3]
          ? "token-keyword"
          : match[4]
            ? "token-decorator"
            : match[5]
              ? "token-type"
              : match[6]
                ? "token-function"
                : match[7]
                  ? "token-number"
                  : "token-constant";
    highlighted += `<span class="${tokenClass}">${escapeHtml(match[0])}</span>`;
    cursor = match.index + match[0].length;
  }
  return highlighted + escapeHtml(source.slice(cursor));
}

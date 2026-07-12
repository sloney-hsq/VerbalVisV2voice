/** Group a flat realtime timeline into user-led conversation turns. */
export function groupTranscriptItems(items = []) {
  const groups = [];
  let current = null;

  for (const item of Array.isArray(items) ? items : []) {
    if (item?.role === "user") {
      current = makeGroup(`turn-${item.id || groups.length + 1}`, item.startedAt);
      groups.push(current);
    } else if (!current) {
      current = makeGroup("turn-session-start", item?.startedAt);
      groups.push(current);
    }

    if (item?.role === "tool") current.actions.push(item);
    else current.messages.push(item);
  }

  return groups;
}

function makeGroup(id, startedAt) {
  return {
    id,
    startedAt: startedAt ?? Date.now(),
    messages: [],
    actions: [],
  };
}

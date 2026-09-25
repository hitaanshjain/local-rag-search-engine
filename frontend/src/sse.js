export function createSSEParser(onEvent) {
  let buffer = "";

  return {
    push(text) {
      buffer = (buffer + text).replace(/\r\n/g, "\n");
      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        let name = "message";
        const dataLines = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) name = line.slice(6).trimStart();
          if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
        }
        if (dataLines.length) onEvent(name, JSON.parse(dataLines.join("\n")));
        boundary = buffer.indexOf("\n\n");
      }
    },
  };
}

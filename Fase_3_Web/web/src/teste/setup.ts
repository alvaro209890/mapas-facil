import "@testing-library/jest-dom/vitest";

/**
 * O jsdom não implementa `Blob.arrayBuffer()` nem `Blob.text()` — e o upload por partes
 * depende dos dois (fatiar o arquivo e calcular o sha256 de cada parte). Sem este polyfill,
 * o teste falha em `fatia.arrayBuffer is not a function`, que não é o erro do produto.
 */
if (typeof Blob !== "undefined" && typeof Blob.prototype.arrayBuffer !== "function") {
  Blob.prototype.arrayBuffer = function arrayBuffer(this: Blob): Promise<ArrayBuffer> {
    return new Promise<ArrayBuffer>((resolve, reject) => {
      const leitor = new FileReader();
      leitor.onload = () => resolve(leitor.result as ArrayBuffer);
      leitor.onerror = () => reject(leitor.error);
      leitor.readAsArrayBuffer(this);
    });
  };
}

if (typeof Blob !== "undefined" && typeof Blob.prototype.text !== "function") {
  Blob.prototype.text = function text(this: Blob): Promise<string> {
    return new Promise<string>((resolve, reject) => {
      const leitor = new FileReader();
      leitor.onload = () => resolve(String(leitor.result ?? ""));
      leitor.onerror = () => reject(leitor.error);
      leitor.readAsText(this);
    });
  };
}

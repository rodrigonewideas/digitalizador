import { useEffect, useState } from "react";

import { api } from "../api/client";

/** Busca a imagem legada do documento (blob autenticado) e entrega um objectURL. */
export function useImagemDocumento(docId: number, versao: "full" | "thumb") {
  const [url, setUrl] = useState<string | null>(null);
  const [falhou, setFalhou] = useState(false);

  useEffect(() => {
    let vivo = true;
    let objeto: string | null = null;
    setUrl(null);
    setFalhou(false);
    (async () => {
      try {
        const blob = await api<Blob>(`/documentos/${docId}/imagem?versao=${versao}`);
        objeto = URL.createObjectURL(blob);
        if (vivo) setUrl(objeto);
        else URL.revokeObjectURL(objeto);
      } catch {
        if (vivo) setFalhou(true);
      }
    })();
    return () => {
      vivo = false;
      if (objeto) URL.revokeObjectURL(objeto);
    };
  }, [docId, versao]);

  return { url, falhou };
}

export function ThumbDocumento({
  docId,
  onAbrir,
  altura = 46,
}: {
  docId: number;
  onAbrir?: () => void;
  altura?: number;
}) {
  const { url, falhou } = useImagemDocumento(docId, "thumb");
  if (falhou)
    return <span className="muted" style={{ fontSize: ".72rem" }}>sem imagem</span>;
  if (!url) return <span className="muted">…</span>;
  return (
    <img
      src={url}
      alt={`Documento ${docId}`}
      style={{ height: altura, borderRadius: 4, cursor: onAbrir ? "zoom-in" : undefined, display: "block" }}
      onClick={onAbrir}
    />
  );
}

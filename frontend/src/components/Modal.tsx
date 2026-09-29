import { useEffect, type ReactNode } from "react";

export function Modal({
  titulo,
  onClose,
  children,
  largura = "42rem",
}: {
  titulo: string;
  onClose: () => void;
  children: ReactNode;
  largura?: string;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal" style={{ maxWidth: largura }} role="dialog" aria-modal="true" aria-label={titulo}>
        <div className="modal-head">
          <h2>{titulo}</h2>
          <button type="button" className="modal-x" onClick={onClose} aria-label="Fechar">
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  titulo,
  mensagem,
  confirmar = "Confirmar",
  perigo = false,
  busy = false,
  onConfirm,
  onClose,
}: {
  titulo: string;
  mensagem: ReactNode;
  confirmar?: string;
  perigo?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal titulo={titulo} onClose={onClose} largura="26rem">
      <p style={{ margin: "0 0 .4rem" }}>{mensagem}</p>
      <div className="modal-foot">
        <button type="button" className="btn ghost" onClick={onClose} disabled={busy}>
          Cancelar
        </button>
        <button type="button" className={perigo ? "btn perigo" : "btn"} onClick={onConfirm} disabled={busy}>
          {busy ? "…" : confirmar}
        </button>
      </div>
    </Modal>
  );
}

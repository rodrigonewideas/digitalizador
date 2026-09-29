-- =============================================================================
-- Seeds de bootstrap (ambiente de DEV / primeira subida, ANTES do ETL)
-- =============================================================================
-- Idempotente. Em produção com ETL, os catálogos (grupo, motivo, tipo_documento,
-- indices, volume_storage) vêm do dump legado — rode estas seeds só num banco
-- limpo de desenvolvimento.
-- =============================================================================

-- Grupo administrador padrão
INSERT INTO grupo (descricao, ativo)
SELECT 'Administradores', true
WHERE NOT EXISTS (SELECT 1 FROM grupo WHERE descricao = 'Administradores');

-- Volume de storage padrão (raízes de exemplo — ajustar aos mounts reais)
INSERT INTO volume_storage (nome, raiz_full, raiz_thumb, raiz_backup, ativo, data_ativo)
SELECT 'LOCAL', '/srv/digitalizador/full', '/srv/digitalizador/thumb',
       '/srv/backup/digitalizador', true, CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM volume_storage WHERE nome = 'LOCAL');

-- Parâmetro global (linha única) apontando para o volume padrão
INSERT INTO parametro (id, volume_gravacao_id, volume_backup_id, volume_thumbnail_id)
SELECT true, v.id, v.id, v.id
FROM volume_storage v
WHERE v.nome = 'LOCAL'
ON CONFLICT (id) DO NOTHING;

-- OBS: o usuário admin inicial é criado pela aplicação (senha com hash Argon2id
-- + fluxo de confirmação de e-mail), não por SQL, para não gravar senha em texto.

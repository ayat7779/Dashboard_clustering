/*
  Ringkasan aman dari query penetapan yang diberikan.
  Tidak mengambil nama pemilik, NIK, nomor telepon, alamat, nomor rangka, atau nomor mesin.
  Ubah rentang tanggal berikut sesuai kebutuhan sinkronisasi.
*/
SELECT
    DATE(a.TglCetakSKPD) AS periode,
    COALESCE((
        SELECT CONCAT(j.Status, ' ', j.NamaUPTUP)
        FROM db_regident_master.dm_wilayahsamsat j
        WHERE j.KodeWilayah = a.KodeLokasiBayar
    ), 'Tidak diketahui') AS wilayah,
    COALESCE(a.PokokPKB, 0) + COALESCE(a.PokokPKBT1, 0) + COALESCE(a.PokokPKBT2, 0)
      + COALESCE(a.PokokPKBT3, 0) + COALESCE(a.PokokPKBT4, 0) + COALESCE(a.PokokPKBT5, 0)
      + COALESCE(a.DendaPKB, 0) + COALESCE(a.DendaPKBT1, 0) + COALESCE(a.DendaPKBT2, 0)
      + COALESCE(a.DendaPKBT3, 0) + COALESCE(a.DendaPKBT4, 0) + COALESCE(a.DendaPKBT5, 0)
      + COALESCE(a.DendaKasPKB, 0) AS realisasi_pkb,
    COALESCE(a.PokokBBN, 0) + COALESCE(a.PokokBBNT1, 0) + COALESCE(a.PokokBBNT2, 0)
      + COALESCE(a.PokokBBNT3, 0) + COALESCE(a.PokokBBNT4, 0) + COALESCE(a.PokokBBNT5, 0)
      + COALESCE(a.DendaBBN, 0) + COALESCE(a.DendaBBNT1, 0) + COALESCE(a.DendaBBNT2, 0)
      + COALESCE(a.DendaBBNT3, 0) + COALESCE(a.DendaBBNT4, 0) + COALESCE(a.DendaBBNT5, 0)
      + COALESCE(a.DendaKasBBN, 0) AS realisasi_bbn,
    COALESCE(a.PokokPKB_Opsen, 0) + COALESCE(a.PokokPKB_OpsenT1, 0) + COALESCE(a.PokokPKB_OpsenT2, 0)
      + COALESCE(a.PokokPKB_OpsenT3, 0) + COALESCE(a.PokokPKB_OpsenT4, 0) + COALESCE(a.PokokPKB_OpsenT5, 0)
      + COALESCE(a.DendaPKB_Opsen, 0) + COALESCE(a.DendaPKB_OpsenT1, 0) + COALESCE(a.DendaPKB_OpsenT2, 0)
      + COALESCE(a.DendaPKB_OpsenT3, 0) + COALESCE(a.DendaPKB_OpsenT4, 0) + COALESCE(a.DendaPKB_OpsenT5, 0) AS opsen_pkb,
    COALESCE(a.PokokBBN_Opsen, 0) + COALESCE(a.DendaBBN_Opsen, 0) AS opsen_bbn
FROM db_regident_dipenda.penetapan a
WHERE a.TglCetakSKPD >= '2026-01-01'
  AND a.TglCetakSKPD < '2026-12-31';

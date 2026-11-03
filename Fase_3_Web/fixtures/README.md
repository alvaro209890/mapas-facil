# `fixtures/` — ZIPs **sintéticos** de teste

Regra dura (**D35**, AP-09): **nenhum dado de cliente entra aqui nem no git**. Nada de recibo do
CAR real, CPF/CNPJ de proprietário, shapefile de imóvel ou `.mxd` de cliente.

Os ZIPs são **gerados** pelo script e **não** são versionados — o CI e o desenvolvedor rodam o
gerador. O gerador chega na tarefa **W4-08** (`gerar_zip_sintetico.py`), com semente fixa.

| Fixture | O que contém | Para que serve |
|---|---|---|
| `imovel_ficticio.zip` | ATP/AVN/AREA_CONSOLIDADA/AUAS em EPSG:4674, polígonos regulares desenhados pelo script, recibo PDF falso ("Fazenda Fictícia Teste", CAR `MT000000/0000`, CPF `000.000.000-00`) | caminho feliz de ponta a ponta |
| `imovel_ficticio_21s.zip` / `_20s.zip` | centroide a 56° W / 60,5° W | escolha de zona UTM |
| `imovel_alongado.zip` | retângulo 3:1 | enquadramento |
| `imovel_sad69.zip` | mesma geometria em SAD69 UTM 22S (EPSG:29192) | conversão SAD69 → SIRGAS (W4-10) |
| `serie_bloco.zip` | 6 "matrículas" contíguas (~12 km) | escala única da série |
| `zip_slip.zip`, `zip_bomba.zip`, `symlink.zip`, `nomes_cp437.zip`, `truncado.zip`, `sem_atp.zip`, `sem_prj.zip` | ataques e erros de importação | segurança e mensagens de erro |

Enquanto o gerador não existe (antes do W4), quem precisar de um ZIP para smoke usa o
`Testes/` local — que é **gitignored** justamente por ter dado real — e **não** copia para cá.

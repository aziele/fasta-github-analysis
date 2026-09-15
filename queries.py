"""Search query definitions used by the GitHub analysis pipeline."""


BROAD_REPOSITORY_QUERY = "repo_fasta"


REPOSITORY_SEARCH_QUERIES = [
    # Broad rescue query
    (BROAD_REPOSITORY_QUERY, "fasta"),

    # FASTA terminology
    ("repo_fasta_file", '"fasta file"'),
    ("repo_fasta_format", '"fasta format"'),
    ("repo_fasta_sequence", '"fasta sequence"'),
    ("repo_fasta_record", '"fasta record"'),

    # Reading, writing, and parsing
    ("repo_fasta_input", '"fasta input"'),
    ("repo_fasta_output", '"fasta output"'),
    ("repo_fasta_parser", '"fasta parser"'),
    ("repo_fasta_reader", '"fasta reader"'),
    ("repo_fasta_parse", '"parse fasta"'),
    ("repo_fasta_read", '"read fasta"'),
    ("repo_fasta_write", '"write fasta"'),

    # Tools and conversion
    ("repo_fasta_converter", '"fasta converter"'),
    ("repo_fasta_tool", '"fasta tool"'),

    # Biological context
    ("repo_fasta_genome", "fasta genome"),
    ("repo_fasta_dna", "fasta dna"),
    ("repo_fasta_protein", "fasta protein"),
    ("repo_fasta_alignment", "fasta alignment"),
    ("repo_fasta_rna", "fasta rna"),
    ("repo_fasta_nucleotide", "fasta nucleotide"),
]


CODE_SEARCH_QUERIES = [
    # Python — Biopython
    ("code_py_seqio_parse_fasta", '"SeqIO.parse" "fasta" extension:py'),
    ("code_py_seqio_read_fasta", '"SeqIO.read" "fasta" extension:py'),
    ("code_py_seqio_write_fasta", '"SeqIO.write" "fasta" extension:py'),
    ("code_py_seqio_index_fasta", '"SeqIO.index" "fasta" extension:py'),
    ("code_py_fastaio", '"Bio.SeqIO.FastaIO" extension:py'),
    ("code_py_seqio_convert_fasta", '"SeqIO.convert" "fasta" extension:py'),
    ("code_py_simple_fasta_parser", '"SimpleFastaParser" extension:py'),
    ("code_py_fasta_two_line_parser", '"FastaTwoLineParser" extension:py'),

    # Python — scikit-bio
    ("code_py_skbio_read_fasta", '"skbio.io.read" "fasta" extension:py'),
    ("code_py_skbio_format_fasta", '"format=\\"fasta\\"" "skbio" extension:py'),

    # Python — Pyteomics
    ("code_py_pyteomics_fasta", '"pyteomics.fasta" extension:py'),
    ("code_py_pyteomics_import_fasta", '"from pyteomics import fasta" extension:py'),

    # Python — FASTA-specific libraries
    ("code_py_pyfastx_fasta", '"pyfastx.Fasta" extension:py'),
    ("code_py_pysam_fastafile", '"pysam.FastaFile" extension:py'),
    ("code_py_pyfaidx_fasta", '"pyfaidx.Fasta" extension:py'),
    ("code_py_fastapy", '"import fastapy" extension:py'),
    ("code_py_pysam_fastxfile", '"pysam.FastxFile" extension:py'),

    # R
    ("code_r_read_fasta", '"read.fasta" extension:R'),
    ("code_r_write_fasta", '"write.fasta" extension:R'),
    ("code_r_writexstringset_fasta", '"writeXStringSet" "fasta" extension:R'),

    # R — Biostrings
    ("code_r_readdnastringset_fasta", '"readDNAStringSet" "fasta" extension:R'),
    ("code_r_readaastringset_fasta", '"readAAStringSet" "fasta" extension:R'),

    # C
    ("code_c_htslib_faidx", '"faidx_fetch_seq"'),

    # C++ — SeqAn
    ("code_cpp_seqan3_fasta", '"seqan3::format_fasta" extension:cpp'),
    ("code_cpp_seqan2_fasta", '"Fasta" "seqan" extension:cpp'),
    ("code_cpp_kseq_init", '"KSEQ_INIT"'),

    # Rust — rust-bio
    ("code_rust_bio_fasta", '"use bio::io::fasta" extension:rs'),

    # Rust — noodles
    ("code_rust_noodles_fasta", '"noodles_fasta" extension:rs'),

    # Rust — needletail
    ("code_rust_needletail_fasta_reader", '"FastaReader" "needletail" extension:rs'),
    ("code_rust_needletail_write_fasta", '"write_fasta" "needletail" extension:rs'),

    # Perl
    ("code_perl_bioperl_fasta", '"Bio::SeqIO" "fasta" extension:pl'),
    ("code_perl_db_fasta", '"Bio::DB::Fasta" extension:pl'),

    # Java — HTSJDK
    ("code_java_htsjdk_fasta", '"htsjdk.samtools.reference.FastaSequenceFile" extension:java'),
    ("code_java_fasta_sequence_file", '"FastaSequenceFile" extension:java'),

    # Java — BioJava
    ("code_java_biojava_fasta_reader", '"FastaReaderHelper" extension:java'),
    ("code_java_biojava_fasta_writer", '"FastaWriterHelper" extension:java'),
    ("code_java_biojava_fasta_reader_direct", '"FastaReader<" extension:java'),
    ("code_java_biojava_fasta_writer_direct", '"FastaWriter<" extension:java'),
    ("code_java_biojava_fasta_streamer", '"FastaStreamer" extension:java'),
    ("code_java_biojava_fasta_parser", '"FastaSequenceParser" extension:java'),

    # Go
    ("code_go_biogo_fasta", '"github.com/biogo/biogo/io/seqio/fasta"'),

    # Julia — FASTX.jl
    ("code_julia_fasta_reader", '"FASTA.Reader" extension:jl'),
    ("code_julia_fasta_writer", '"FASTA.Writer" extension:jl'),
    ("code_julia_fastareader", '"FASTAReader" extension:jl'),
    ("code_julia_fastawriter", '"FASTAWriter" extension:jl'),
    ("code_julia_fasta_record", '"FASTA.Record" extension:jl'),

    # Command-line tools
    ("code_seqkit_faidx", '"seqkit faidx"'),
    ("code_seqkit_fq2fa", '"seqkit fq2fa"'),
    ("code_emboss_seqret_fasta", '"seqret" "fasta"'),
]
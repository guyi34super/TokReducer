use clap::{Parser, Subcommand};
use tokreducer::{TokReducer, Level};

#[derive(Parser)]
#[command(name = "tokreducer", version = "1.0.0")]
#[command(about = "TokReducer — Token Compression Protocol for LLMs")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Compress a prompt using TokReducer
    Compress {
        /// The prompt to compress
        prompt: String,
        /// Compression level (0-3)
        #[arg(short, long, default_value = "2")]
        level: u8,
    },
    /// Start the REST API server
    Serve {
        /// Port to listen on
        #[arg(short, long, default_value = "8080")]
        port: u16,
        /// Host to bind to
        #[arg(long, default_value = "0.0.0.0")]
        host: String,
        /// Default compression level
        #[arg(short, long, default_value = "2")]
        level: u8,
    },
}

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Compress { prompt, level } => {
            let tok = TokReducer::new(Level::from_u8(level));
            let compressed = tok.compress(&prompt);
            let orig = tok.count(&prompt);
            let comp = tok.count(&compressed);
            let pct = tok.reduction_pct(&prompt, &compressed);

            println!("Original:   {prompt}");
            println!("Compressed: {compressed}");
            println!("Tokens:     {orig} → {comp} ({pct:.1}% reduction)");
        }
        Commands::Serve { port, host, level: default_level } => {
            serve(host, port, default_level).await;
        }
    }
}

async fn serve(host: String, port: u16, default_level: u8) {
    use axum::{routing::{get, post}, Json, Router};
    use serde::{Deserialize, Serialize};

    #[derive(Deserialize)]
    struct CompressReq {
        prompt: String,
        level: Option<u8>,
    }

    #[derive(Serialize)]
    struct CompressRes {
        compressed: String,
        original_tokens: usize,
        compressed_tokens: usize,
        reduction_pct: f64,
    }

    #[derive(Deserialize)]
    struct DecompressReq {
        text: String,
    }

    #[derive(Serialize)]
    struct DecompressRes {
        decompressed: String,
    }

    #[derive(Serialize)]
    struct HealthRes {
        status: String,
        version: String,
    }

    let dl = default_level;

    let app = Router::new()
        .route("/health", get(|| async {
            Json(HealthRes {
                status: "ok".into(),
                version: "1.0.0".into(),
            })
        }))
        .route("/compress", post(move |Json(req): Json<CompressReq>| async move {
            let level = Level::from_u8(req.level.unwrap_or(dl));
            let tok = TokReducer::new(level);
            let compressed = tok.compress(&req.prompt);
            Json(CompressRes {
                original_tokens: tok.count(&req.prompt),
                compressed_tokens: tok.count(&compressed),
                reduction_pct: tok.reduction_pct(&req.prompt, &compressed),
                compressed,
            })
        }))
        .route("/decompress", post(|Json(req): Json<DecompressReq>| async move {
            let tok = TokReducer::new(Level::Medium);
            Json(DecompressRes {
                decompressed: tok.decompress(&req.text),
            })
        }));

    let addr = format!("{host}:{port}");
    println!("TokReducer API listening on {addr}");
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

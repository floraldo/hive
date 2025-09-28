# EcoSystemiser v3.0 - Intelligent Energy System Design & Optimization

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

EcoSystemiser is a comprehensive platform for designing, optimizing, and analyzing sustainable energy systems. Built with advanced Discovery Engine capabilities for multi-objective optimization and uncertainty analysis.

## ✨ Key Features

- **🧬 Discovery Engine**: Advanced GA/NSGA-II and Monte Carlo solvers
- **🌍 Climate Integration**: NASA POWER, Meteostat, ERA5, PVGIS data sources
- **📊 Professional Reporting**: Interactive HTML reports with Plotly visualizations
- **⚡ High Performance**: Parallel processing and efficient algorithms
- **🔧 Production Ready**: Docker deployment with comprehensive monitoring
- **🎯 User Friendly**: Clean CLI and web dashboard interfaces

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Clone and navigate
git clone https://github.com/your-org/hive.git
cd hive/apps/ecosystemiser

# Start all services
docker-compose up -d

# Access interfaces
open http://localhost:8000/docs    # API Documentation
open http://localhost:5000         # Reporting Dashboard
open http://localhost:8501         # Streamlit Dashboard
```

### Development Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the demo
python examples/run_full_demo.py

# Use the CLI
python -m ecosystemiser.cli --help
```

## 📖 Documentation

- **[Deployment Guide](./DEPLOYMENT.md)** - Production deployment instructions
- **[API Documentation](http://localhost:8000/docs)** - Interactive API reference
- **[Roadmap](./ROADMAP.md)** - Future development plans
- **[Changelog](./CHANGELOG.md)** - Version history and updates

## 🎯 Quick Examples

### Climate Data Retrieval
```bash
# Get Berlin weather data
ecosys climate get --loc "Berlin, DE" --year 2023 --vars temp_air,ghi,wind_speed
```

### Energy System Optimization
```bash
# Run genetic algorithm optimization
ecosys discover optimize config.yaml --population 50 --generations 100 --report

# Monte Carlo uncertainty analysis
ecosys discover analyze config.yaml --method monte_carlo --samples 1000 --report
```

### Generate Reports
```bash
# Create HTML report from results
ecosys report generate results/study_20240928_143022.json --type auto
```

## 🏗️ Architecture

EcoSystemiser follows a modular, event-driven architecture:

```
┌─────────────────────────────────────────────────────────┐
│                    Web Interfaces                       │
│  API Docs    │  Reporting    │   Dashboard             │
│  (FastAPI)   │   (Flask)     │  (Streamlit)            │
└─────────────┬─────────────────┬───────────────────────┘
              │                 │
    ┌─────────▼──────────┐  ┌───▼──────────┐
    │  Discovery Engine  │  │ Profile Loader│
    │  • GA/NSGA-II     │  │ • Climate APIs │
    │  • Monte Carlo     │  │ • Data QC      │
    │  • Optimization    │  │ • Caching      │
    └─────────┬──────────┘  └───┬───────────┘
              │                 │
        ┌─────▼─────────────────▼─────┐
        │      Hive Event Bus         │
        │   (Redis-based messaging)   │
        └─────────────────────────────┘
```

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test suite
python -m pytest tests/test_discovery_engine_e2e.py -v

# Integration tests
python scripts/test_presentation_layer.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋 Support

- **Issues**: [GitHub Issues](https://github.com/your-org/hive/issues)
- **Documentation**: [User Guide](./docs/)
- **Community**: [Discussions](https://github.com/your-org/hive/discussions)
- **Email**: support@ecosystemiser.com

## 🌟 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) for high-performance APIs
- [Plotly](https://plotly.com/python/) for interactive visualizations
- [NSGA-II](https://pymoo.org/) for multi-objective optimization
- [xarray](http://xarray.pydata.org/) for climate data processing
- [Streamlit](https://streamlit.io/) for rapid dashboard development

---

**Made with ❤️ by the EcoSystemiser Team**
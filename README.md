# ASTRA Web API
API wrapper for ASTRA simulation code-

# Startup

Build image and start container

    docker compose stop && docker compose up -d --build


# Troubleshooting

### Problem: Rootless containers on the remote host quit once the user terminates the ssh session.
    
This is not an issue of Docker. Linux stops processes started by a normal user if loginctl is configured to not use 
lingering, to prevent normal users to keep long-running processes executing in the system.
In order to fix the problem, one can enable lingering by executing 

    loginctl enable-linger $UID

on the remote host.
Source: [Stackoverflow](https://stackoverflow.com/a/73312070)

# Cite this project

If you use this project in your scientific work and find it useful, you could use the following BibTeX entry to cite this project.

      @misc{astra-web,
        Author = {A. Klemps},
        Title = {ASTRA-Web},
        Year = {2024},
        publisher = {GitHub},
        journal = {https://github.com/AlexanderKlemps/astra-generator},
        version = {0.1}
      }

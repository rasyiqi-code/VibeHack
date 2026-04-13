document.addEventListener('DOMContentLoaded', () => {
    // 1. Smooth Scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });

    // 2. Terminal Typing Animation (Simulated)
    const lines = [
        { text: "vibe@hack:~$ vibehack --target https://corp.target", class: "" },
        { text: "🤖 AI Thought: Found 200 OK on /phpmyadmin/ and /admin/.", class: "t-dim" },
        { text: "🤖 AI Thought: Proposing LFI test on /article?id=...", class: "t-dim" },
        { text: "⚡ Suggested Command: curl -s \"https://target/art...\"", class: "t-yellow" },
        { text: "✓ Exploit Success: Read /etc/passwd", class: "t-green" },
        { text: "vibe@hack:~$ ", class: "" }
    ];

    const terminalBody = document.getElementById('terminal-content');
    
    function resetTerminal() {
        terminalBody.innerHTML = '<div class="terminal-dots"><span></span><span></span><span></span></div>';
        let i = 0;
        
        function typeNextLine() {
            if (i < lines.length) {
                const lineDiv = document.createElement('div');
                lineDiv.className = 'line ' + lines[i].class;
                lineDiv.innerHTML = lines[i].text;
                
                if (i === lines.length - 1) {
                    lineDiv.innerHTML += '<span class="cursor">_</span>';
                }
                
                terminalBody.appendChild(lineDiv);
                i++;
                setTimeout(typeNextLine, 1200);
            } else {
                setTimeout(resetTerminal, 4000);
            }
        }
        
        typeNextLine();
    }

    // Initialize typing after a short delay
    // setTimeout(resetTerminal, 1000);

    // 3. Scroll Reveal Animation for Feature Cards
    const observerOptions = {
        threshold: 0.1
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .tm-content').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.6s ease-out';
        observer.observe(el);
    });
});

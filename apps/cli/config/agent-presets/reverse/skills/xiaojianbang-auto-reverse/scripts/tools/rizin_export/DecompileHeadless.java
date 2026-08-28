// Ghidra headless post-script: decompile every function and write pseudo-C to files.
// Written for xiaojianbang-auto-reverse rizin_export.py. Place beside /next to the
// rizin_export helper and pass its directory via -scriptPath.
//
// Usage (from rizin_export.py): analyzeHeadless <projectDir> <name> -import <so> \
//   -postScript DecompileHeadless.java -scriptPath <this-dir> [-deleteProject]
//
// Decompiler plugin name is best-effort: try "Decompiler" then "Decompiler"
// (the Ghidra bundled decompiler). If the function-graph decompiler is
// available it is used; otherwise the pluginName fallback is attempted.

import java.io.File;
import java.io.PrintWriter;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Program;
import ghidra.program.model.address.Address;

public class DecompileHeadless extends GhidraScript {

    @Override
    public void run() throws Exception {
        Program program = getCurrentProgram();
        String outDir = System.getenv("GHIDRA_DECOMP_OUT");
        File dir = new File(outDir != null ? outDir : "ghidra_pseudocode");
        if (!dir.exists()) {
            dir.mkdirs();
        }

        DecompInterface decompiler = new DecompInterface();
        decompiler.toggleCCode(true);
        decompiler.openProgram(program);

        FunctionIterator funcs = program.getFunctionManager().getFunctions(true);
        PrintWriter index = new PrintWriter(new File(dir, "index.txt"), "UTF-8");
        int count = 0;
        for (Function f : funcs) {
            String name = f.getName();
            Address entry = f.getEntryPoint();
            DecompileResults res = decompiler.decompileFunction(f, 60, monitor);
            String body = res.getDecompiledFunction() != null
                ? res.getDecompiledFunction().getC()
                : ("// decompile failed: " + name);
            String safe = name.replaceAll("[^A-Za-z0-9_.-]", "_");
            if (safe.length() == 0) {
                safe = "func_" + Long.toHexString(entry.getOffset());
            }
            PrintWriter pw = new PrintWriter(new File(dir, safe + ".c"), "UTF-8");
            pw.println("// " + name + " @ " + entry);
            pw.println(body);
            pw.close();
            index.println(name + "\t" + entry + "\t" + safe + ".c");
            count++;
        }
        index.close();
        decompiler.dispose();
        println("decompiled functions: " + count);
    }
}

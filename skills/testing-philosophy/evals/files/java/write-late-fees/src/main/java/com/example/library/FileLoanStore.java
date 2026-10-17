package com.example.library;

import java.io.IOException;
import java.io.Reader;
import java.io.UncheckedIOException;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.util.Optional;
import java.util.Properties;

/** Production store: one properties file per loan inside a directory owned by this service. */
public final class FileLoanStore implements LoanStore {
    private final Path dir;

    public FileLoanStore(Path dir) {
        this.dir = dir;
        try {
            Files.createDirectories(dir);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    @Override
    public Optional<Loan> find(String loanId) {
        Path file = fileFor(loanId);
        if (!Files.exists(file)) {
            return Optional.empty();
        }
        Properties p = new Properties();
        try (Reader r = Files.newBufferedReader(file)) {
            p.load(r);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        String returned = p.getProperty("returnedOn", "");
        return Optional.of(new Loan(
                p.getProperty("id"),
                p.getProperty("memberEmail"),
                MemberType.valueOf(p.getProperty("memberType")),
                Long.parseLong(p.getProperty("replacementCostCents")),
                LocalDate.parse(p.getProperty("checkedOutOn")),
                LocalDate.parse(p.getProperty("dueOn")),
                returned.isEmpty() ? null : LocalDate.parse(returned),
                Long.parseLong(p.getProperty("feeCents"))));
    }

    @Override
    public void save(Loan loan) {
        Properties p = new Properties();
        p.setProperty("id", loan.id());
        p.setProperty("memberEmail", loan.memberEmail());
        p.setProperty("memberType", loan.memberType().name());
        p.setProperty("replacementCostCents", Long.toString(loan.replacementCostCents()));
        p.setProperty("checkedOutOn", loan.checkedOutOn().toString());
        p.setProperty("dueOn", loan.dueOn().toString());
        p.setProperty("returnedOn", loan.returnedOn() == null ? "" : loan.returnedOn().toString());
        p.setProperty("feeCents", Long.toString(loan.feeCents()));
        Path tmp = dir.resolve(loan.id() + ".tmp");
        try (Writer w = Files.newBufferedWriter(tmp)) {
            p.store(w, null);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        try {
            Files.move(tmp, fileFor(loan.id()), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
    }

    private Path fileFor(String loanId) {
        if (!loanId.matches("[A-Za-z0-9-]+")) {
            throw new IllegalArgumentException("invalid loan id: " + loanId);
        }
        return dir.resolve(loanId + ".loan");
    }
}
